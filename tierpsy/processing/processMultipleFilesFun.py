# -*- coding: utf-8 -*-
"""
Created on Tue Aug  9 00:26:10 2016

@author: ajaver
"""
import os
import argparse

from tierpsy.processing.CheckFilesForProcessing import CheckFilesForProcessing
from tierpsy.processing.ProcessLocal import ProcessLocalParser
from tierpsy.processing.helper import find_valid_files, \
remove_border_checkpoints, get_results_dir, get_masks_dir
from tierpsy.processing.run_multi_cmd import RunMultiCMD

from tierpsy.helper.params import TrackerParams
from tierpsy.helper.params.docs_process_param import dflt_args_list, process_valid_options

class ProcessMultipleFilesParser(argparse.ArgumentParser):
    def __init__(self):
        description = "Process worm video in the local drive using several parallel processes"
        super().__init__(description=description)

        for name, dflt_val, help in dflt_args_list:

            args_d = {'help' : help}
            if isinstance(dflt_val, bool):
                args_d['action'] = 'store_true'
            else:
                args_d['default'] = dflt_val
                if isinstance(dflt_val, (int, float)):
                    args_d['type'] = type(dflt_val)

            if isinstance(dflt_val, (list, tuple)):
                args_d['nargs'] = '+'

            if name in process_valid_options:
                args_d['choices'] = process_valid_options[name]

            self.add_argument('--' + name, **args_d)

def processMultipleFilesFun(
        video_dir_root,
        mask_dir_root,
        results_dir_root,
        tmp_dir_root,
        json_file,
        videos_list,
        pattern_include,
        pattern_exclude,
        max_num_process,
        refresh_time,
        only_summary,
        force_start_point='',
        end_point='',
        is_copy_video=False,
        analysis_checkpoints=[],
        unmet_requirements = False,
        copy_unfinished = False,
        is_debug = True
        ):

    assert video_dir_root or mask_dir_root

    # get a name for the directories if they were not given
    if not video_dir_root:
        video_dir_root = mask_dir_root

    if not mask_dir_root:
        mask_dir_root = get_masks_dir(video_dir_root)

    if not results_dir_root:
        results_dir_root = get_results_dir(mask_dir_root)

    param = TrackerParams(json_file)

    json_file = param.json_file

    if not analysis_checkpoints:
      analysis_checkpoints = param.p_dict['analysis_checkpoints'].copy()



    if True:#os.name == 'nt' or 'm4v' in pattern_include:
        # This is giving problems in windows, specially while frozen. It shouldn't affect too much since it only speed up the check up of the files progress
        is_parallel_check = False
    else:
        is_parallel_check = True

    is_parallel_check = False

    remove_border_checkpoints(analysis_checkpoints, force_start_point, 0)
    remove_border_checkpoints(analysis_checkpoints, end_point, -1)

    walk_args = {'root_dir': video_dir_root,
                 'pattern_include' : pattern_include,
                  'pattern_exclude' : pattern_exclude}

    check_args = {'video_dir_root': video_dir_root,
                  'mask_dir_root': mask_dir_root,
                  'results_dir_root' : results_dir_root,
                  'tmp_dir_root' : tmp_dir_root,
                  'json_file' : json_file,
                  'analysis_checkpoints': analysis_checkpoints,
                  'is_copy_video': is_copy_video,
                  'copy_unfinished': copy_unfinished,
                  'is_parallel_check': is_parallel_check}

    #get the list of valid videos
    if not videos_list:
        valid_files = find_valid_files(**walk_args)
    else:
        with open(videos_list, 'r') as fid:
            valid_files = fid.read().split('\n')
            #valid_files = [os.path.realpath(x) for x in valid_files]

    files_checker = CheckFilesForProcessing(**check_args)

    cmd_list = files_checker.filterFiles(valid_files, print_cmd=is_debug)

    if unmet_requirements:
         files_checker._printUnmetReq()
    elif not only_summary:
        RunMultiCMD(
            cmd_list,
            local_obj = ProcessLocalParser,
            max_num_process = max_num_process,
            refresh_time = refresh_time,
            is_debug = is_debug)

def tierpsy_process():
    args = ProcessMultipleFilesParser().parse_args()
    processMultipleFilesFun(**vars(args))
