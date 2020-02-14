# -*- coding: utf-8 -*-
"""
Created on Wed May 18 18:22:12 2016

@author: ajaver
"""
import os

import cv2
import tables
import numpy as np

from tierpsy.helper.params import read_fps
from tierpsy.helper.misc import TimeCounter, print_flush


def getSubSampleVidName(masked_image_file):
    #used by AnalysisPoints.py and CheckFinished.py
    return masked_image_file.replace('.hdf5', '_subsample.avi')


def _getCorrectedTimeVec(fid, tot_frames):
    '''time vector used to account for missing frames'''
    try:
        timestamp_ind = fid.get_node('/timestamp/raw')[:]
        #remove any nan, I notice that sometimes the last number is a nan
        timestamp_ind = timestamp_ind[~np.isnan(timestamp_ind)]
        tot_timestamps = int(timestamp_ind[-1])

        if timestamp_ind.size < tot_frames-1 or tot_timestamps < tot_frames-1: #invalid timestamp
            #if there is not valid frames skip
            raise ValueError

    except (tables.exceptions.NoSuchNodeError, ValueError, IndexError):
        return np.arange(tot_frames)

    #make sure to compensate for missing frames, so the video will have similar length.
    tt_vec = np.full(tot_timestamps+1, np.nan)
    current_frame = 0
    for ii in range(tot_timestamps+1):
        tt_vec[ii] = current_frame
        current_timestamp = timestamp_ind[current_frame]
        if current_timestamp <= ii:
            current_frame += 1

    return tt_vec

def createSampleVideo(masked_image_file,
                    sample_video_name = '',
                    time_factor = 8,
                    size_factor = 5,
                    skip_factor = 2,
                    dflt_fps=30,
                    codec='MPEG',
                    shift_bgnd = False):
    #skip factor is to reduce the size of the movie by using less frames (so we use 15fps for example instead of 30fps)

    #%%
    if not sample_video_name:
        sample_video_name = getSubSampleVidName(masked_image_file)

    # initialize timers
    base_name = masked_image_file.rpartition('.')[0].rpartition(os.sep)[-1]
    progressTime = TimeCounter('{} Generating subsampled video.'.format(base_name))

    with tables.File(masked_image_file, 'r') as fid:
        masks = fid.get_node('/mask')
        tot_frames, im_h, im_w = masks.shape
        im_h, im_w = im_h//size_factor, im_w//size_factor

        fps = read_fps(masked_image_file, dflt_fps)

        tt_vec = _getCorrectedTimeVec(fid, tot_frames)
        #%%
        #codec values that work 'H264' #'MPEG' #XVID
        vid_writer = cv2.VideoWriter(sample_video_name, \
                            cv2.VideoWriter_fourcc(*codec), fps/skip_factor, (im_w,im_h), isColor=False)
        assert vid_writer.isOpened()


        if shift_bgnd:
            #lazy bgnd calculation, just take the last and first frame and get the top 95 pixel value
            mm = masks[[0,-1], :, :]
            _bgnd_val = np.percentile(mm[mm!=0], [97.5])[0]



        for frame_number in range(0, tot_frames, int(time_factor*skip_factor)):
            current_frame = int(tt_vec[frame_number])
            img = masks[current_frame]

            if shift_bgnd:
               img[img==0] = _bgnd_val

            im_new = cv2.resize(img, (im_w,im_h))
            vid_writer.write(im_new)


            if frame_number % (500*time_factor) == 0:
                # calculate the progress and put it in a string
                print_flush(progressTime.get_str(frame_number))

        vid_writer.release()
        print_flush(progressTime.get_str(frame_number) + ' DONE.')

#%%
if __name__ == '__main__':

    #mask_file_name = '/Volumes/behavgenom_archive$/Avelino/Worm_Rig_Tests/Agar_Test/MaskedVideos/Agar_Screening_101116/N2_N10_F1-3_Set1_Pos3_Ch6_12112016_002739.hdf5'
    #masked_image_file = '/Volumes/behavgenom_archive$/Avelino/Worm_Rig_Tests/Agar_Test/MaskedVideos/Agar_Screening_101116/unc-9_N3_F1-3_Set1_Pos3_Ch4_12112016_002739.hdf5'
#    masked_image_file = r'C:\Users\wormrig\Documents\GitHub\Multiworm_Tracking\Tests\data\test_1\MaskedVideos\Capture_Ch1_18062015_140908.hdf5'
#    createSampleVideo(masked_image_file)

    from tqdm import tqdm
    from pathlib import Path
    from tierpsy.helper.misc import RESERVED_EXT

    # folders:
    hd = Path('/Volumes/diskAshur3T/Leah')
    dd = Path('/Volumes/behavgenom$/Serena/foodpatch/mp4/Leah')
    # get list of files and filter it
    fnames = list(hd.rglob('*.hdf5'))
    fnames = [f for f in fnames if not any([ext in str(f) for ext in RESERVED_EXT])]
    # parameters for compression
    subsample_params = {'time_factor': 100,
                        'skip_factor': 1,
                        'dflt_fps': 25,
                        'codec': 'H264',
                        'size_factor': 1}
    # loop on files and compress
    for masked_image_file in tqdm(fnames):
        # get output file name
        sample_video_name = Path(str(masked_image_file).replace('.hdf5','.mp4'))
        sample_video_name = dd / sample_video_name.relative_to(hd)
        sample_video_name.parent.mkdir(parents=True, exist_ok=True)
        # do compression
        try:
            createSampleVideo(str(masked_image_file), str(sample_video_name),
                              **subsample_params)
        except:
            print('Didnt work:')
            print(masked_image_file)

