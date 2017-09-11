#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Sep  5 18:31:24 2017

@author: ajaver
"""
import numpy as np
import pandas as pd
import tables

from tierpsy_features import get_timeseries_features

from tierpsy.helper.misc import TimeCounter, print_flush, get_base_name, TABLE_FILTERS
from tierpsy.helper.params import read_fps

def _h_get_timeseries_feats_table(features_file, 
                                  velocity_delta_time = 1/3,
                                  curvature_window = None):
    timeseries_features = []
    fps = read_fps(features_file)
    with pd.HDFStore(features_file, 'r') as fid:
        trajectories_data = fid['/trajectories_data']
    #only use data that was skeletonized
    trajectories_data = trajectories_data[trajectories_data['skeleton_id']>=0]
    
    
    trajectories_data_g = trajectories_data.groupby('worm_index_joined')
    progress_timer = TimeCounter('')
    base_name = get_base_name(features_file)
    tot_worms = len(trajectories_data_g)
    def _display_progress(n):
            # display progress
        dd = " Smoothing skeletons. Worm %i of %i done." % (n+1, tot_worms)
        print_flush(
            base_name +
            dd +
            ' Total time:' +
            progress_timer.get_time_str())
    
    _display_progress(0)
    
    
    for ind_n, (worm_index, worm_data) in enumerate(trajectories_data_g):
        with tables.File(features_file, 'r') as fid:
            skel_id = worm_data['skeleton_id'].values
            args = []
            for p in ('skeletons', 'widths', 'dorsal_contours', 'ventral_contours'):
                 dd = fid.get_node('/coordinates/' + p)
                 if len(dd.shape) == 3:
                     args.append(dd[skel_id, :, :])
                 else:
                     args.append(dd[skel_id, :])
                
        feats = get_timeseries_features(*args, 
                                        fps = fps,
                                        delta_time = velocity_delta_time, #delta time in seconds to calculate the velocity
                                        curvature_window = curvature_window
                                        )
        feats = feats.astype(np.float32)
        feats['worm_index'] = np.int32(worm_index)
        feats['timestamp'] = worm_data['timestamp_raw'].values
        
        #move the last fields to the first columns
        cols = feats.columns.tolist()
        cols = cols[-2:] + cols[:-2]
        timeseries_features.append(feats[cols])
        
        _display_progress(ind_n+1)
        
    timeseries_features = pd.concat(timeseries_features, ignore_index=True)
    
    with tables.File(features_file, 'r+') as fid:
        if '/timeseries_features' in fid:
            fid.remove_node('/timeseries_features')

        fid.create_table(
                '/',
                'timeseries_features',
                obj = timeseries_features.to_records(index=False),
                filters = TABLE_FILTERS)

def get_tierpsy_features(
        features_file,
        velocity_delta_time = 1/3,
        curvature_window = 7
        ):
    
    _h_get_timeseries_feats_table(features_file, 
                                velocity_delta_time,
                                curvature_window
                                )
    
if __name__ == '__main__':
    #base_file = '/Volumes/behavgenom_archive$/single_worm/finished/mutants/gpa-10(pk362)V@NL1147/food_OP50/XX/30m_wait/clockwise/gpa-10 (pk362)V on food L_2009_07_16__12_55__4'
    #base_file = '/Users/ajaver/Documents/GitHub/tierpsy-tracker/tests/data/WT2/Results/WT2'
    #base_file = '/Users/ajaver/Documents/GitHub/tierpsy-tracker/tests/data/AVI_VIDEOS/Results/AVI_VIDEOS_4'
    base_file = '/Users/ajaver/Documents/GitHub/tierpsy-tracker/tests/data/GECKO_VIDEOS/Results/GECKO_VIDEOS'
    is_WT2 = False
    
    
    features_file = base_file + '_featuresN.hdf5'
    
    get_tierpsy_features(
        features_file,
        velocity_delta_time = 1/3,
        curvature_window = 7
        )
