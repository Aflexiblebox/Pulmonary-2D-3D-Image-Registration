import torch
from torch.optim.lr_scheduler import ReduceLROnPlateau
from tools.data_loader import Dataset
from torch.utils.data import DataLoader
import math
from tools.instanceExam import InstanceExam
from tools.tool_functions import *
from torch.utils.tensorboard import SummaryWriter
from tools.models_init import optional_init


def val(Dataset_loader, net, loss_function, device):
    val_loss = 0
    with torch.no_grad():
        for i, (imgs, target) in enumerate(Dataset_loader):
            imgs = imgs.to(device)
            target = target.to(device)
            prediction = net(imgs)
            loss = loss_function(prediction, target)
            val_loss += loss
    return (val_loss / (i + 1))


def train(args, cfg):
    # 初始化
    exam_process_dict = cfg['EXAM_PROCESS']
    model_methods, lossfunction_methods = optional_init()

    setup_seed(12)
    # 超参数设定
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    batch_size = args.batch_size
    loss_wcoeff = torch.FloatTensor([2 / math.sqrt(6), 1 / math.sqrt(6), 1 / math.sqrt(6)]).to(device)
    img_folder = args.train_DRR_dir
    label_folder = args.CT_dir if cfg["PREDICTION_MODE"] == "CT" else args.PCA_dir

    # 进行各个exam
    for exam_cfg in exam_process_dict:
        exam_instance = InstanceExam(args, cfg, exam_cfg)
        # 生成log文件
        logger = get_logger(filename=os.path.join(exam_instance.log_dir, exam_instance.work_fileName + "_train.log"),
                            verbosity=1,
                            name=exam_instance.work_fileName)

        # 生成csv文件
        csv_writer = get_csv(
            filename=os.path.join(exam_instance.csv_dir, exam_instance.work_fileName + "_train.csv"),
            header=["cur_epoch", "train_loss", "test_loss"])

        # 生成run文件
        run_writer = SummaryWriter(exam_instance.tensorboard_dir)

        model = model_methods[exam_instance.model_method](exam_instance.inChannel_num).to(device)
        loss_fn = lossfunction_methods[exam_instance.lossFunction_method](loss_wcoeff)
        opt = torch.optim.Adam(model.parameters(), lr=args.lr)
        scheduler = ReduceLROnPlateau(opt, mode='min', verbose=True, patience=3)
        # 数据加载
        dataset = Dataset(img_dir=img_folder,
                          label_dir=label_folder,
                          input_mode=exam_instance.input_mode,
                          preImg_num=args.preImg_num,
                          model_type=exam_instance.model_type,
                          prediction_mode=exam_instance.prediction_mode,
                          data_shape=exam_instance.data_shape
                          )
        test_size = int(len(dataset) * args.val_ratio)
        train_size = int(len(dataset) - test_size)
        train_dataset, test_dataset = torch.utils.data.random_split(dataset=dataset,
                                                                    lengths=[train_size, test_size],
                                                                    generator=torch.Generator().manual_seed(12))
        train_data_loader = DataLoader(train_dataset, shuffle=True, batch_size=batch_size)
        test_data_loader = DataLoader(test_dataset, shuffle=True, batch_size=batch_size)

        # 训练参数设定
        logger.info(
            "DATASET:" + str(exam_instance.dataset)
            + "\tMODEL_TYPE:" + str(exam_instance.model_type)
            + "\tPREDICTION_MODE:" + str(exam_instance.prediction_mode)
            + '\tCOMPARE_MODE:' + str(exam_instance.compare_mode)
            + '\tINPUT_MODE:' + str(exam_instance.input_mode)
            + "\tPREIMG_NUM:" + str(exam_instance.preImg_num)
            + "\tMODEL:" + str(exam_instance.model_method)
            + "\tLOSSFUNCTION:" + str(exam_instance.lossFunction_method)
        )
        logger.info("Epoch:" + str(args.EPOCH) + "\ttrain_dataset_num:" + str(train_size) + "\ttest_dataset_num:" + str(
            test_size))
        logger.info("---" * 100)
        loss_epoch = []

        logger.info('start training!')
        for epoch in range(args.EPOCH):
            loss_mse = 0
            for i, (imgs, target) in enumerate(train_data_loader):
                imgs = imgs.to(device)
                target = target.to(device)
                prediction = model(imgs)
                loss_item = loss_fn(target, prediction)
                loss_mse += loss_item
                opt.zero_grad()  # 清空上一步残余更新参数值
                loss_item.backward()  # 误差反向传播，计算参数更新值
                opt.step()
                print("(epoch:%d--step:%d)------->loss:%.3f" % (epoch, i, loss_item.item()))
            loss_mse = loss_mse / (i + 1)
            loss_epoch.append(loss_mse.cpu().detach().numpy())

            val_loss = val(test_data_loader, model, loss_fn, device)
            print('epoch:%d  train_loss:%.3f  test_loss:%.3f' % (epoch, loss_mse.item(), val_loss.item()))
            scheduler.step(loss_mse)
            logger.info(
                'Epoch:[{}/{}]\t train_loss={:.3f}\t test_loss={:.3f}'.format((epoch + 1), args.EPOCH, loss_mse.item(),
                                                                              val_loss.item()))
            csv_writer.writerow({"cur_epoch": (epoch + 1), "train_loss": loss_mse.item(), "test_loss": val_loss.item()})
            run_writer.add_scalars("train_progress", {"train_loss": loss_mse.item(), "val_loss": val_loss.item()})

            if (epoch + 1) % args.EPOCH == 0:
                cur_ckpt_file_name = os.path.join(exam_instance.cur_ckpt_dir, str(epoch + 1) + ".pth")
                torch.save(model.state_dict(), cur_ckpt_file_name)

        logger.info('finish training!')
        logging.shutdown()
        run_writer.close()


if __name__ == '__main__':
    args, cfg = load_cfg(yaml_path="./tools/cfg/pca_spaceAndTime.yaml")
    train(args, cfg)
