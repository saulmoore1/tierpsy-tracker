import pandas as pd
from functools import partial
import numpy as np
import tables
import os

try:
    from keras.models import load_model
except ImportError:
    import warnings
    warnings.warn("`keras` is not found, this will break contour finding ",
                  + "on *_AEX analysis, and may break filter trajectories ",
                  + "unless pytorch is being used")

try:
    import torch
except ImportError:
    import warnings
    warnings.warn("`pytorch` not found, this may break filter trajectories ")

from tierpsy.analysis.ske_create.helperIterROI import generateMoviesROI, getROIFixSize
from tierpsy.helper.params import read_fps
from .pytorchModelHelper import (
    prep_for_pytorch, load_pytorch_model, MODEL_ROIS_TRAINED_SIZE)


def shift_and_normalize(data):
    '''
    shift worms values by an approximation of the removed background. I used the top95 of the unmasked area.
    I am assuming region of the background is kept.
    '''
    data_m = data.view(np.ma.MaskedArray)
    data_m.mask = data==0
    if data.ndim == 3:
        sub_d = np.percentile(data, 95, axis=(1,2)) #let's use the 95th as the value of the background
        data_m -= sub_d[:, None, None]
    else:
        sub_d = np.percentile(data, 95)
        data_m -= sub_d

    data /= 255
    return data


def reformat_for_model(data, is_pytorch=False):
    '''
    Reformat image for the model.
    '''

    shift_and_normalize(data)
    if not is_pytorch:
        #expand for channel (keras tf backend required)
        data = np.expand_dims(data, axis=3).astype(np.float32)
    else:
        # pytorch requires [0, 1] images, 4d: [batch, c, h, w]
        data = prep_for_pytorch(data)

    return data


def getWormProba(worms_in_frame, roi_size, model, is_pytorch=False):
    '''calculate the probability of worm using the CLASS_MODEL and save
    into table_to_save. table_to_save must be passed by reference'''
    indexes, worm_imgs, roi_corners = getROIFixSize(worms_in_frame, roi_size)

    worms_roi_f = reformat_for_model(worm_imgs, is_pytorch=is_pytorch)
    if not is_pytorch:
        # keras syntax
        worm_prob = model.predict(worms_roi_f, verbose=0)[:, 1]
    else:
        # pytorch needs tensor objects first
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        worms_roi_f_tensor = torch.tensor(worms_roi_f).to(device)
        # this saves memory disabling autograd
        with torch.no_grad():
            output = model(worms_roi_f_tensor)
            worm_prob = output.data.cpu().numpy()[:, 1]
    return indexes, worm_prob


def indentifyValidWorms(masked_file,
                         trajectories_data,
                         model_path,
                         frame_subsampling):
    ''' Use a pre-trained nn to identify blobs that correspond to worms or worm aggregates

        frame_subsamplig - number of frames skipped. We do not need to calculate in
                            every frame. A value of near the number of fps is sensible.
    '''
    if model_path.endswith('.pth'):
        is_pytorch = True
        model = load_pytorch_model(model_path)
        roi_size = MODEL_ROIS_TRAINED_SIZE
    else:
        is_pytorch = False
        model = load_model(model_path)
        roi_size = model.input_shape[2]

    proba_func = partial(
        getWormProba, roi_size=roi_size, model=model, is_pytorch=is_pytorch)

    frame_numbers = trajectories_data['frame_number'].unique()

    frame_numbers = frame_numbers[::frame_subsampling]
    trajectories_data_rec = trajectories_data[trajectories_data['frame_number'].isin(frame_numbers)].copy()


    base_name = masked_file.rpartition('.')[0].rpartition(os.sep)[-1]
    progress_prefix =  base_name + ' Identifying valid worm trajectories.'

    #get generators to get the ROI and calculate the worm probabilities from them
    ROIs_generator = generateMoviesROI(masked_file,
                                         trajectories_data_rec,
                                         roi_size=roi_size,
                                         progress_prefix=progress_prefix)

    worm_probs_gen = map(proba_func, ROIs_generator)

    #here we really execute the code
    out_per_frame = [x for x in worm_probs_gen]

    #pull all the outputs into a nice format and add the results into the table
    indexes, worm_probs = [np.concatenate(x) for x in zip(*out_per_frame)]
    trajectories_data_rec['worm_prob'] = pd.Series(worm_probs, indexes)

    worm_ind_prob = trajectories_data_rec.groupby('worm_index_joined').aggregate({'worm_prob':np.median})['worm_prob']
    valid_worms_indexes = worm_ind_prob.index[worm_ind_prob>0.5]

    return valid_worms_indexes

def filterModelWorms(masked_image_file, trajectories_data, model_path, frame_subsampling = -1):
    if frame_subsampling ==-1:
        #use the expected number of frames per seconds as the subsampling period
        frame_subsampling = read_fps(masked_image_file)
        frame_subsampling = int(frame_subsampling)

    valid_worms = indentifyValidWorms(masked_image_file,
                                        trajectories_data,
                                        model_path,
                                        frame_subsampling)

    good_rows = trajectories_data['worm_index_joined'].isin(valid_worms)
    trajectories_data = trajectories_data[good_rows].copy()
    trajectories_data['skeleton_id'] = np.arange(len(trajectories_data))
    return trajectories_data



