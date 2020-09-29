#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun  4 10:30:17 2018
@author: avelinojaver
"""
from tierpsy.features.tierpsy_features.summary_stats import get_summary_stats
from tierpsy.summary.helper import augment_data, add_trajectory_info
from tierpsy.summary.filtering import filter_trajectories
from tierpsy.helper.params import read_fps, read_microns_per_pixel
from tierpsy.helper.misc import WLAB,print_flush
from tierpsy.analysis.split_fov.helper import was_fov_split
from tierpsy.analysis.split_fov.FOVMultiWellsSplitter import FOVMultiWellsSplitter

import pandas as pd
import pdb

#%%
def time_to_frame_nb(time_windows,time_units,fps,timestamp,fname):
    """
    Converts the time windows to units of frame numbers (if they were defined in seconds).
    It also defines the end frame of a window, if the index is set to -1 (end).
    """
    from copy import deepcopy

    if timestamp.empty:
        return

    time_windows_frames = deepcopy(time_windows)

    if time_units == 'seconds':
        assert fps!=-1, 'Cannot convert time windows to frame numbers. Frames per second ratio not known.'
        for iwin, win in enumerate(time_windows_frames):
            for iinterval in range(len(win)):
                for ilim in range(2):
                    if time_windows_frames[iwin][iinterval][ilim]!=-1:
                        time_windows_frames[iwin][iinterval][ilim] = \
                            round(time_windows_frames[iwin][iinterval][ilim]*fps)

    last_frame = timestamp.sort_values().iloc[-1]
    for iwin, win in enumerate(time_windows_frames):
        for iinterval in range(len(win)):
            # If a window ends with -1, replace with the frame number of the
            # last frame (or the start frame of the window+1 if window out of bounds)
            if time_windows_frames[iwin][iinterval][1]==-1:
                time_windows_frames[iwin][iinterval][1] = \
                    max(last_frame+1, time_windows_frames[iwin][iinterval][0])

            # If a window is out of bounds, print warning
            if time_windows_frames[iwin][iinterval][0]>last_frame:
                print_flush(
                    'Warning: The start time of interval '+
                    '{}/{} '.format(iinterval+1, len(win)) +
                    'of window {} '.format(iwin) +
                    'is out of bounds of file \'{}\'.'.format(fname))

    return time_windows_frames

def no_attr_flush(attr, fname):
    if attr=='fps':
        out = ['seconds', 'frames_per_second', fname, 'frame numbers']
    elif attr=='mpp':
        out = ['microns', 'microns_per_pixel', fname, 'pixels']

    print_flush(
        """
        Warning: some of the summarizer input were given in {0}, but the {1}
        ratio for file \'{2}\' is unknown. Give input in {3} instead.
        """.format(*out)
        )
    return

def _no_fps(time_units, fps, fname):
    if fps==-1:
        if time_units=='seconds':
            no_attr_flush('fps', fname)
            return True

    return False

def _match_units(filter_params, fps, fname):
    """
    author: EM
    The filtering thresholds must match the timeseries units. If the right
    conversion is not possible, then check_ok is False, and the feature
    summaries will not be calculated for this file.

    """
    from copy import deepcopy

    if filter_params is None:
        return filter_params, True

    all_units = filter_params['units']+[filter_params['time_units']]

    cfilter_params = deepcopy(filter_params)

    if fps==-1:
        # In this case, all time-related timeseries will be in frames.
        # If thresholds have been defined in seconds there is no way to convert.
        if 'seconds' in all_units:
            no_attr_flush('fps', fname)
            return cfilter_params, False

    else:
        # In this case, all time-related timeseries will be in seconds.

        # We always want the time_units for traj_length in frames
        if filter_params['time_units']=='seconds' and \
            filter_params['min_traj_length'] is not None:
                cfilter_params['min_traj_length'] = \
                    filter_params['min_traj_length']*fps

        # If the timeseries therholds are defined in seconds, no conversion is
        # necessary
        # If the timeseries thresholds are defined in frames, we need to convert
        # to seconds
        if 'frame_numbers' in filter_params['units']:
            ids = [i for i,x in enumerate(filter_params['units']) if x=='frame_numbers']
            for i in ids:
                if filter_params['min_thresholds'][i] is not None:
                    cfilter_params['min_thresholds'][i]= \
                        filter_params['min_thresholds'][i]/fps
                if filter_params['max_thresholds'][i] is not None:
                    cfilter_params['max_thresholds'][i]= \
                        filter_params['max_thresholds'][i]/fps

    mpp = read_microns_per_pixel(fname)

    if mpp==-1:
        # In this case, all distance-related timeseries will be in pixels.
        # If thresholds have been defined in microns there is no way to convert.
        if 'microns' in all_units:
            no_attr_flush('mpp', fname)
            return cfilter_params, False
    else:
        # In this case, all distance-related timeseries will be in microns.
        # If the timeseries threholds are defined in micorns, no conversion is
        # necessary
        # If the timeseries thresholds are defined in pixels, we need to convert
        # to microns
        if filter_params['distance_units']=='pixels' and \
            filter_params['min_distance_traveled'] is not None:
                cfilter_params['min_distance_traveled'] = \
                    filter_params['min_distance_traveled']*mpp
        if 'pixels' in filter_params['units']:
            ids = [i for i,x in enumerate(filter_params['units']) if x=='pixels']
            for i in ids:
                if filter_params['min_thresholds'][i] is not None:
                    cfilter_params['min_thresholds'][i]= \
                        filter_params['min_thresholds'][i]*mpp
                if filter_params['max_thresholds'][i] is not None:
                    cfilter_params['max_thresholds'][i]= \
                        filter_params['max_thresholds'][i]*mpp

    return cfilter_params, True

#%%
def read_data(fname, filter_params, time_windows, time_units, fps, is_manual_index):
    """
    Reads the timeseries_data and the blob_features for a given file within every time window.
    return:
        timeseries_data_list: list of timeseries_data for each time window (length of lists = number of windows)
        blob_features_list: list of blob_features for each time window (length of lists = number of windows)
    """
    import numpy as np
    # EM: If time_units=seconds and fps is not defined, then return None with warning of no fps.
    #     Make this check here, to avoid wasting time reading the file
    if _no_fps(time_units, fps, fname):
        return

    cfilter_params, check_ok = _match_units(filter_params, fps, fname)
    if not check_ok:
        return

    with pd.HDFStore(fname, 'r') as fid:
        timeseries_data = fid['/timeseries_data']
        blob_features = fid['/blob_features']

        if is_manual_index:
            #keep only data labeled as worm or worm clusters
            valid_labels = [WLAB[x] for x in ['WORM', 'WORMS']]
            trajectories_data = fid['/trajectories_data']
            if not 'worm_index_manual' in trajectories_data:
                #no manual index, nothing to do here
                return

            good = trajectories_data['worm_label'].isin(valid_labels)
            good = good & (trajectories_data['skeleton_id'] >= 0)
            skel_id = trajectories_data['skeleton_id'][good]

            timeseries_data = timeseries_data.loc[skel_id]
            timeseries_data['worm_index'] = trajectories_data['worm_index_manual'][good].values
            timeseries_data = timeseries_data.reset_index(drop=True)

            blob_features = blob_features.loc[skel_id].reset_index(drop=True)

        if timeseries_data.empty:
            #no data, nothing to do here
            return
        # convert time windows to frame numbers for the given file
        time_windows_frames = time_to_frame_nb(
            time_windows, time_units, fps, timeseries_data['timestamp'], fname
            )

        # EM: Filter trajectories
        if cfilter_params is not None:
            timeseries_data, blob_features = \
                filter_trajectories(timeseries_data, blob_features, **cfilter_params)

        if timeseries_data.empty:
            #no data, nothing to do here
            return

        # EM: extract the timeseries_data and blob_features corresponding to each
        # time window and store them in a list (length of lists = number of windows)
        timeseries_data_list = []
        blob_features_list = []
        for window in time_windows_frames:
            in_window = []
            for interval in window:
                in_interval = (timeseries_data['timestamp']>=interval[0]) & \
                              (timeseries_data['timestamp']<interval[1])
                in_window.append(in_interval.values)
            in_window = np.any(in_window, axis=0)
            timeseries_data_list.append(timeseries_data.loc[in_window, :].reset_index(drop=True))
            blob_features_list.append(blob_features.loc[in_window].reset_index(drop=True))

    return timeseries_data_list, blob_features_list

def count_skeletons(timeseries):
    cols = [col for col in timeseries.columns if col.startswith('eigen')]
    return (~timeseries[cols].isna().any(axis=1)).sum()

#%%
def tierpsy_plate_summary(
        fname, filter_params, time_windows, time_units,
        only_abs_ventral=False, selected_feat=None,
        is_manual_index=False, delta_time=1/3):
    """
    Calculate the plate summaries for a given file fname, within a given time window
    (units of start time and end time are in frame numbers).
    """
    fps = read_fps(fname)
    data_in = read_data(
        fname, filter_params, time_windows, time_units, fps, is_manual_index)

    # if manual annotation was chosen and the trajectories_data does not contain
    # worm_index_manual, then data_in is None
    # if time_windows in seconds and fps is not defined (fps=-1), then data_in is None
    if data_in is None:
        return [pd.DataFrame() for iwin in range(len(time_windows))]

    timeseries_data, blob_features = data_in

    # was the fov split in wells? only use the first window to detect that,
    # and to extract the list of well names
    is_fov_tosplit = was_fov_split(fname)
#    is_fov_tosplit = False

    if is_fov_tosplit:
        fovsplitter = FOVMultiWellsSplitter(fname)
        good_wells_df = fovsplitter.wells[['well_name','is_good_well']].copy()
        # print(good_wells_df)

    # initialize list of plate summaries for all time windows
    plate_feats_list = []
    for iwin,window in enumerate(time_windows):
        if is_fov_tosplit == False:
            plate_feats = get_summary_stats(
                timeseries_data[iwin], fps,  blob_features[iwin], delta_time,
                only_abs_ventral=only_abs_ventral,
                selected_feat=selected_feat
                )
            plate_feats['n_skeletons'] = count_skeletons(timeseries_data[iwin])
            plate_feats_list.append(pd.DataFrame(plate_feats).T)
        else:
            # get list of well names in this time window
            # (maybe some wells looked empty during a whole window,
            # this prevents errors later on)
            well_names_list = list(set(timeseries_data[iwin]['well_name']) - set(['n/a']))
            # create a list of well-specific, one-line long dataframes
            well_feats_list = []
            for well_name in well_names_list:
                # find entries in timeseries_data[iwin] belonging to the right well
                idx_well = timeseries_data[iwin]['well_name'] == well_name
                well_feats = get_summary_stats(
                    timeseries_data[iwin][idx_well].reset_index(), fps,
                    blob_features[iwin][idx_well].reset_index(), delta_time,
                    only_abs_ventral=only_abs_ventral,
                    selected_feat=selected_feat
                    )
                well_feats['n_skeletons'] = count_skeletons(timeseries_data[iwin][idx_well])
                # first prepend the well_name_s to the well_feats series,
                # then transpose it so it is a single-row dataframe,
                # and append it to the well_feats_list
                well_name_s = pd.Series({'well_name':well_name})
                well_feats_list.append(pd.DataFrame(pd.concat([well_name_s,well_feats])).T)
            # check: did we find any well?
            if len(well_feats_list) == 0:
                plate_feats_list.append(pd.DataFrame())
            else:
                # now concatenate all the single-row df in well_feats_list in a single df
                # and append it to the growing list (1 entry = 1 window)
                plate_feats = pd.concat(well_feats_list, ignore_index=True, sort=False)
#                import pdb; pdb.set_trace()
                plate_feats = plate_feats.merge(good_wells_df,
                                                on='well_name',
                                                how='left')
                plate_feats_list.append(plate_feats)

    return plate_feats_list


def tierpsy_trajectories_summary(
        fname, filter_params, time_windows, time_units,
        only_abs_ventral=False, selected_feat=None,
        is_manual_index=False, delta_time=1/3):
    """
    Calculate the trajectory summaries for a given file fname, within a given time window
    (units of start time and end time are in frame numbers).
    """
    fps = read_fps(fname)
    data_in = read_data(
        fname, filter_params, time_windows, time_units, fps, is_manual_index)
    if data_in is None:
        return [pd.DataFrame() for iwin in range(len(time_windows))]
    timeseries_data, blob_features = data_in

    is_fov_tosplit = was_fov_split(fname)
    #    is_fov_tosplit = False
    if is_fov_tosplit:
        fovsplitter = FOVMultiWellsSplitter(fname)
        good_wells_df = fovsplitter.wells[['well_name','is_good_well']].copy()
        # print(good_wells_df)

    # initialize list of summaries for all time windows
    all_summaries_list = []
    # loop over time windows
    for iwin,window in enumerate(time_windows):
        if timeseries_data[iwin].empty:
            all_summary = pd.DataFrame([])
        else:
            # initialize list of trajectory summaries for given time window
            all_summary = []
            # loop over worm indexes (individual trajectories)
            for w_ind, w_ts_data in timeseries_data[iwin].groupby('worm_index'):
                w_blobs = blob_features[iwin].loc[w_ts_data.index]

                w_ts_data = w_ts_data.reset_index(drop=True)
                w_blobs = w_blobs.reset_index(drop=True)

                worm_feats = get_summary_stats(
                    w_ts_data, fps,  w_blobs, delta_time,
                    only_abs_ventral=only_abs_ventral,
                    selected_feat=selected_feat
                    ) # returns empty dataframe when w_ts_data is empty
                worm_feats['n_skeletons'] = count_skeletons(w_ts_data)
                worm_feats = pd.DataFrame(worm_feats).T
                worm_feats = add_trajectory_info(
                    worm_feats, w_ind, w_ts_data, fps,
                    is_fov_tosplit=is_fov_tosplit)

                all_summary.append(worm_feats)
            # concatenate all trajectories in given time window into one dataframe
            all_summary = pd.concat(all_summary, ignore_index=True, sort=False)
            # attach whether the wells was good or bad
            if is_fov_tosplit:  #  but only do this if we have wells
                all_summary = all_summary.merge(good_wells_df,
                                                on='well_name',
                                                how='left')

        # add dataframe to the list of summaries for all time windows
        all_summaries_list.append(all_summary)

    return all_summaries_list

#%%

def tierpsy_plate_summary_augmented(
        fname, filter_params, time_windows, time_units,
        only_abs_ventral = False, selected_feat = None,
        is_manual_index = False, delta_time = 1/3,
        **fold_args):

    fps = read_fps(fname)
    data_in = read_data(
        fname, filter_params, time_windows, time_units, fps, is_manual_index)
    if data_in is None:
        return [pd.DataFrame() for iwin in range(len(time_windows))]
    timeseries_data, blob_features = data_in

    # initialize list of summaries for all time windows
    all_summaries_list = []

    # loop over time windows
    for iwin,window in enumerate(time_windows):
        if timeseries_data[iwin].empty:
            all_summary = pd.DataFrame([])
        else:
            fold_index = augment_data(timeseries_data[iwin], fps=fps, **fold_args)
            # initialize list of augmented plate summaries for given time window
            all_summary = []
            # loop over folds
            for i_fold, ind_fold in enumerate(fold_index):


                timeseries_data_r = timeseries_data[iwin][ind_fold].reset_index(drop=True)
                blob_features_r = blob_features[iwin][ind_fold].reset_index(drop=True)

                plate_feats = get_summary_stats(
                    timeseries_data_r, fps,  blob_features_r, delta_time,
                    only_abs_ventral=only_abs_ventral,
                    selected_feat=selected_feat
                    )

                plate_feats['n_skeletons'] = count_skeletons(timeseries_data_r)
                plate_feats = pd.DataFrame(plate_feats).T
                plate_feats.insert(0, 'i_fold', i_fold)

                all_summary.append(plate_feats)

            # concatenate all folds in given time window into one dataframe
            all_summary = pd.concat(all_summary, ignore_index=True, sort=False)

        # add dataframe to the list of summaries for all time windows
        all_summaries_list.append(all_summary)

    return all_summaries_list


if __name__ == '__main__':

    fname='/Users/em812/Data/Tierpsy_GUI/test_results_2/N2_worms10_CSAA016712_1_Set3_Pos4_Ch2_14072017_184843_featuresN.hdf5'
    # fname='/Users/lferiani/Desktop/Data_FOVsplitter/short/Results/drugexperiment_1hr30minexposure_set1_bluelight_20190722_173404.22436248/metadata_featuresN.hdf5'
    # fname='/Users/lferiani/Desktop/Data_FOVsplitter/evgeny/Results/20190808_subset/evgeny_plate01_r1_20190808_114758.22956805/metadata_featuresN.hdf5'
    # fname = '/Users/lferiani/Hackathon/multiwell_tierpsy/12_FEAT_TIERPSY/Results/20191205/syngenta_screen_run1_bluelight_20191205_151104.22956805/metadata_featuresN.hdf5'
    is_manual_index = False


    fold_args = dict(
                 n_folds = 2,
                 frac_worms_to_keep = 0.8,
                 time_sample_seconds = 10*60
                 )

    filter_params = None

    # time_windows = [[0,10000],[10000,15000],[10000000,-1]]
    # time_units = 'frameNb'

    # time_windows = [[0,60],[120,-1],[10000000,-1]]
    # time_windows = [[[0,60]], [[0,120]], [[150,200], [250,300]], [[10000000,-1]]]
    # time_units = 'seconds'
    time_windows = [[[0,60]], [[0,120]], [[150,200], [250,300]], [[10000000,-1]]]
    time_units = 'frame_numbers'

    fps = 25

    timeseries_list, blob_list = read_data(fname, filter_params, time_windows, time_units, fps, is_manual_index)
    # summary = tierpsy_plate_summary(fname,time_windows,time_units)
    # summary = tierpsy_trajectories_summary(fname,time_windows,time_units)
    # summary = tierpsy_plate_summary_augmented(fname,time_windows,time_units,is_manual_index=False,delta_time=1/3,**fold_args)

