import os
import json

import torch
import numpy as np
from tqdm import tqdm
from .utils import load_video, load_dimension_info
from .third_party.grit_model import DenseCaptioning

import logging
logging.basicConfig(level = logging.INFO,format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_dect_from_grit(model, image_arrays):
    pred = []
    if type(image_arrays) is not list:
        image_arrays = image_arrays.numpy()
    with torch.no_grad():
        for frame in image_arrays:
            ret = model.run_caption_tensor(frame)
            cur_pred = []
            if len(ret[0])<1:
                cur_pred.append(['',''])
            else:
                for idx, cap_det in enumerate(ret[0]):
                    cur_pred.append([cap_det[0], cap_det[2][idx]])
            pred.append(cur_pred)
    return pred

def check_generate(color_key, object_key, predictions):
    cur_object_color, cur_object = 0, 0
    for frame_pred in predictions:
        object_flag, color_flag = False, False
        for pred in frame_pred:
            if object_key == pred[1]:
                object_flag =True
                if color_key in pred[0]:
                    color_flag = True
        if color_flag:
            cur_object_color+=1
        if object_flag:
            cur_object +=1
    return cur_object, cur_object_color

def color(model, video_dict, device):
    success_frame_count, frame_count = 0,0
    video_results = []
    for info in tqdm(video_dict):
        if 'auxiliary_info' not in info:
            raise "Auxiliary info is not in json, please check your json."
        # print(info)
        color_info = info['auxiliary_info']['color']
        object_info = info['prompt']
        object_info = object_info.replace('a ','').replace('an ','').replace(color_info,'').strip()
        for video_path in info['video_list']:
            video_tensor = load_video(video_path)
            cur_video_pred = get_dect_from_grit(model, video_tensor.permute(0,2,3,1))
            cur_object, cur_object_color = check_generate(color_info, object_info, cur_video_pred)
            if cur_object>0:
                cur_success_frame_rate = cur_object_color/cur_object
            else:
                cur_success_frame_rate = 1.
            success_frame_count += cur_object_color
            frame_count += cur_object
            video_results.append({'video_path': video_path, 'video_results': cur_success_frame_rate})
    success_rate = success_frame_count / frame_count
    return success_rate, video_results
        

def compute_color(json_dir, device, submodules_dict):
    dense_caption_model = DenseCaptioning(device)
    dense_caption_model.initialize_model(**submodules_dict)
    logger.info("Initialize detection model success")
    _, prompt_dict_ls = load_dimension_info(json_dir, dimension='color', lang='en')
    all_results, video_results = color(dense_caption_model, prompt_dict_ls, device)
    return all_results, video_results