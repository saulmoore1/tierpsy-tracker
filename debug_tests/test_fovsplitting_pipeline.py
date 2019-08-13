# -*- coding: utf-8 -*-


from tierpsy.processing.processMultipleFilesFun import processMultipleFilesFun
from tierpsy.processing.ProcessLocal import ProcessLocalParser
from tierpsy.processing.ProcessWorker import ProcessWorkerParser, ProcessWorker
from tierpsy.helper.params.docs_process_param import dflt_args_list, process_valid_options
import subprocess
#processMultipleFilesFun(analysis_checkpoints=[], 
#                        copy_unfinished=False, 
#                        end_point='', 
#                        force_start_point='', 
#                        is_copy_video=False, 
#                        is_debug=True, 
#                        json_file='/Users/lferiani/Desktop/Data_FOVsplitter/loopbio_rig_new_.json', 
#                        mask_dir_root='', 
#                        max_num_process=7, 
#                        only_summary=False, 
#                        pattern_exclude='', 
#                        pattern_include='*.yaml', 
#                        refresh_time=10.0, 
#                        results_dir_root='', 
#                        tmp_dir_root='/Users/lferiani/Tmp', 
#                        unmet_requirements=False, 
#                        video_dir_root='/Users/lferiani/Desktop/Data_FOVsplitter/RawVideos/20190308_48wptest_short_20190308_155935.22436248', 
#                        videos_list='')

# the above function sbould basically do the same (since I'm only calling it on one video) as running in the CLI
#'/anaconda3/envs/tierpsy_dev/bin/python' '/Users/lferiani/Tierpsy/tierpsy-tracker/tierpsy/processing/ProcessLocal.py' '/Users/lferiani/Desktop/Data_FOVsplitter/RawVideos/20190308_48wptest_short_20190308_155935.22436248/metadata.yaml' --masks_dir '/Users/lferiani/Desktop/Data_FOVsplitter/MaskedVideos/20190308_48wptest_short_20190308_155935.22436248' --results_dir '/Users/lferiani/Desktop/Data_FOVsplitter/Results/20190308_48wptest_short_20190308_155935.22436248' --tmp_mask_dir '/Users/lferiani/Tmp/MaskedVideos/' --tmp_results_dir '/Users/lferiani/Tmp/Results/' --json_file '/Users/lferiani/Desktop/Data_FOVsplitter/loopbio_rig_new_.json' --analysis_checkpoints 'COMPRESS'

imgstore_name = 'drugexperiment_1hr30minexposure_set1_bluelight_20190722_173404.22436248/'

rootdir = '/Users/lferiani/Desktop/Data_FOVsplitter/short/'
rawvideosdir = rootdir + 'RawVideos/' + imgstore_name
maskedvideosdir = rootdir + 'MaskedVideos/' + imgstore_name
resultsdir = rootdir + 'Results/' + imgstore_name

raw_video = rawvideosdir + 'metadata.yaml'
masked_image_file = maskedvideosdir + 'metadata.hdf5'    
features_file = resultsdir + 'metadata_featuresN.hdf5'
skeletons_file = resultsdir + 'metadata_skeletons.hdf5'

json_file = '/Users/lferiani/Desktop/Data_FOVsplitter/loopbio_rig_96WP_upright_Hydra05.json'
# restore features after previous step before testing    
#import shutil
#shutil.copy(features_file.replace('.hdf5','.bk'), features_file)


# don't pass the path to python if calling it as a function
# compress
#sys_argv_list = ['/Users/lferiani/Tierpsy/tierpsy-tracker/tierpsy/processing/ProcessLocal.py',
#                 raw_video,
#                 '--masks_dir', maskedvideosdir,
#                 '--results_dir', resultsdir,
#                 '--json_file', json_file,
#                 '--analysis_checkpoints', 'COMPRESS']

#sys_argv_list = ['/Users/lferiani/Tierpsy/tierpsy-tracker/tierpsy/processing/ProcessLocal.py',
#                 masked_image_file,
#                 '--masks_dir', maskedvideosdir,
#                 '--results_dir', resultsdir,
#                 '--json_file', json_file,
#                 '--analysis_checkpoints', 'TRAJ_CREATE',
#                                            'TRAJ_JOIN',
#                                            'SKE_INIT',
#                                            'BLOB_FEATS']

sys_argv_list = ['/Users/lferiani/Tierpsy/tierpsy-tracker/tierpsy/processing/ProcessLocal.py',
                 masked_image_file,
                 '--masks_dir', maskedvideosdir,
                 '--results_dir', resultsdir,
                 '--json_file', json_file,
                 '--analysis_checkpoints',  'SKE_CREATE',
                                            'SKE_FILT',
                                            'SKE_ORIENT',
                                            'INT_PROFILE',
                                            'INT_SKE_ORIENT',
                                            'FEAT_INIT',
                                            'FEAT_TIERPSY']


local_obj = ProcessLocalParser(sys_argv_list)

worker_cmd = local_obj.start()      # until now, no tmp file has been created

# here take the cmd string that you could give to the terminal, and give it to python instead
# giving the worker)cmd to the terminal starts the analysis
worm_parser = ProcessWorkerParser()

# translate cmd list to a dictionary. vars returns the __dict__ of an object
# in this case since ProcessWorkerParser is a subclass of argParse, a Namespace is returned, 
# so __dict__ is what we want to read and vars() does that
args = vars(worm_parser.parse_args(worker_cmd[2:]))
    
# this is the function that actually does the job
ProcessWorker(**args, cmd_original = subprocess.list2cmdline(sys_argv_list))

#clear temporary files
local_obj.clean()    

