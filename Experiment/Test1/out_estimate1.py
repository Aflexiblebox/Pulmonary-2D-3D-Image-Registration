import numpy as np
import os
import pandas as pd
from tools.tool_functions import *
import pandas
from tools.config import get_args
from tools.estimate_methods import *
import csv


def estimate_calc(model_name, real_PCA_numpy, predict_PCA_numpy, real_CT_numpy, predict_CT_numpy,
                  estimate_methods_list):
    estimate_method_function = {
        "MAE": MAE,
        "MAE_percentage": MAE_percentage,
        "R2": R2,
        "MAD": MAE,
        "MAD_percentage": MAE_percentage,
        "NCC": NCC,
        "SSIM": SSIM
    }
    estimate_data = []
    for estimate_method in estimate_methods_list:
        # 评价 PCA
        if estimate_method in ["MAE", "R2", "MAE_percentage"]:
            estimate_data.append(estimate_method_function[estimate_method](real_PCA_numpy, predict_PCA_numpy))
        # 评价 图像
        else:
            estimate_data.append(estimate_method_function[estimate_method](real_CT_numpy, predict_CT_numpy))
    return estimate_data


def composite_all_excel(all_excel_path):
    all_excel_list = os.listdir(all_excel_path)
    dataframe_list = []
    for excel_name in all_excel_list:
        excel_path = os.path.join(all_excel_path, excel_name)
        dataframe = pd.read_csv(excel_path, sep=',', index_col=0, header=0)
        dataframe_list.append(dataframe.values)
    composite_dataframe_mean = pd.DataFrame(np.mean(dataframe_list, axis=0), index=dataframe.index,
                                            columns=dataframe.columns)
    composite_dataframe_std = pd.DataFrame(np.std(dataframe_list, axis=0), index=dataframe.index,
                                           columns=dataframe.columns)
    composite_dataframe_mean.to_csv(os.path.join(all_excel_path, "composite_out_CTs_mean.csv"), header=True, index=True,
                                    sep=',')
    composite_dataframe_std.to_csv(os.path.join(all_excel_path, "composite_out_CTs_std.csv"), header=True, index=True,
                                   sep=',')


if __name__ == '__main__':
    args = get_args()
    estimate_data = {}
    # 根目录
    root_path = get_poject_path("Pulmonary-2D-3D-Image-Registration")
    # out_path
    num_cp = get_fileNum(get_filename(__file__))
    testName = get_testName(__file__)  # TEST1'
    experiment_dir = get_experimentDir(num_cp, root_path, testName,
                                       args.gen_pca_method)  # E:\code\pycharm\PCA\Experiment\Test1/PCA_origin/model_cp
    out_dir = os.path.join(experiment_dir, "anayle")
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    # 评估方法
    estimate_methods_list = ["MAE", "MAE_percentage", "R2", "MAD", "MAD_percentage", "NCC", "SSIM"]
    # 获取CT_list
    real_CT_path = os.path.join(root_path, args.real_ct)
    # 获取PCA_frame
    PCA_frame_path = os.path.join(root_path, args.pca_frame)
    pca_frame = pd.read_csv(PCA_frame_path, index_col=0).T
    for i in range(9):
        # real_PCA
        real_PCA_numpy = np.array(trim(pca_frame["origin"][i].split("[")[1].split("]")[0].split(" ")))

        # real_CT
        real_CT_numpy = load_odd_file(os.path.join(real_CT_path, "ct_" + str(i + 1) + ".bin")).reshape(150, 256,
                                                                                                       256).transpose(1,
                                                                                                                      2,
                                                                                                                      0)
        print("real_" + str(i + 1))

        all_predict_CT_path = os.path.join(root_path, args.predict_ct)
        model_name_list = os.listdir(all_predict_CT_path)
        for model_name in model_name_list:
            # predict_ct
            predict_CT_path = os.path.join(all_predict_CT_path, model_name, "predict_ct_" + str(i + 1))
            print(model_name, "predict_" + str(i))
            predict_CT_numpy = load_odd_file(predict_CT_path).reshape(150, 256, 256).transpose(1, 2, 0)
            # predict_pca
            predict_PCA_numpy = np.array(
                trim(pca_frame[model_name.split("(")[0]][i].split("[")[1].split("]")[0].split(" ")))
            # 评估函数
            estimate_data_odd_list = estimate_calc(model_name, real_PCA_numpy, predict_PCA_numpy, real_CT_numpy,
                                                   predict_CT_numpy, estimate_methods_list)
            estimate_data[model_name] = estimate_data_odd_list
        estimate_frame = pd.DataFrame(estimate_data, index=estimate_methods_list)
        estimate_frame.to_csv(os.path.join(out_dir, "estimate_out_csv", "estimate_out_CT" + str(i + 1) + ".csv"),
                              sep=",", index=True, header=True)

    all_excel_path = os.path.join(out_dir, "estimate_out_csv")
    composite_all_excel(all_excel_path)
