import os
import time
import subprocess
import threading
import obspython as obs
import obswebsocket
from obswebsocket import obsws, events, requests

enabled = False
debug_mode = False
delete_source = False
hostname = "localhost"
port = 4444
password = "secret"
channel_settings = None
recording_dir = ""
recording_output = ""
ffmpeg_mapped_args = None


def debug_print(*args):
    global debug_mode
    if debug_mode:
        print("[DAC]", *args)


# Taken from https://www.calazan.com/how-to-check-if-a-file-is-locked-in-python/
def is_locked(filepath):
    """Checks if a file is locked by opening it in append mode.
    If no exception thrown, then the file is not locked.
    """
    locked = None
    file_object = None
    if os.path.exists(filepath):
        try:
            debug_print("Trying to open %s." % filepath)
            buffer_size = 8
            # Opening file in append mode and read the first 8 characters.
            file_object = open(filepath, 'a', buffer_size)
            if file_object:
                print("%s is not locked." % filepath)
                locked = False
        except IOError as message:
            debug_print("File is locked (unable to open in append mode). %s." % message)
            locked = True
        finally:
            if file_object:
                file_object.close()
                debug_print("%s closed." % filepath)
    else:
        debug_print("%s not found." % filepath)
    return locked


# Taken from https://www.calazan.com/how-to-check-if-a-file-is-locked-in-python/
def wait_for_files(filepaths):
    """Checks if the files are ready.

    For a file to be ready it must exist and can be opened in append
    mode.
    """
    wait_time = 5
    for filepath in filepaths:
        # If the file doesn't exist, wait wait_time seconds and try again
        # until it's found.
        while not os.path.exists(filepath):
            debug_print("%s hasn't arrived. Waiting %s seconds." % (filepath, wait_time))
            time.sleep(wait_time)
        # If the file exists but locked, wait wait_time seconds and check
        # again until it's no longer locked by another process.
        while is_locked(filepath):
            debug_print("%s is currently in use. Waiting %s seconds." % (filepath, wait_time))
            time.sleep(wait_time)


# This class does most of the work by making it so OBS doesn't lock up while we demux the recording
class MyDemuxThread(threading.Thread):
    def run(self):
        global ffmpeg_mapped_args, recording_dir, recording_output, delete_source
        local_recording_output_file_path = recording_output  # Make a copy of the output so we can start recording right away
        path = local_recording_output_file_path + '_demux'
        os.makedirs(path)
        wait_for_files([local_recording_output_file_path])
        debug_print("calling", 'ffmpeg', '-i', local_recording_output_file_path, *ffmpeg_mapped_args)
        log_output = open(os.path.join(path, 'ffmpeg_output.txt'), 'w')
        process = subprocess.run(['ffmpeg', '-i', local_recording_output_file_path, *ffmpeg_mapped_args],
                                 stdout=log_output, stderr=log_output, cwd=path)
        log_output.close()
        debug_print("subprocess returned with code", process.returncode)
        if delete_source and process.returncode == 0:
            debug_print("removing source file", local_recording_output_file_path)
            os.remove(local_recording_output_file_path)
        pass


# Generates the output params for ffmpeg used when we finish recording
def generate_output_params():
    global channel_settings, ffmpeg_mapped_args
    debug_print("updating ffmpeg params with new mappings")
    channels = []
    ffmpeg_mapped_args = []
    for setting in channel_settings:
        item = setting.split('|', maxsplit=1)
        channel = {'id': item[0]}
        if len(item) > 1:
            channel['name'] = item[1]
        else:
            channel['name'] = channel['id']
        channels.append(channel)
        debug_print("channel is defined as", channel)

    # maybe we want to either use ffprobe to determine the file extension or allow the user to set it in the settings
    for channel in channels:
        ext = 'm4a'
        if channel['id'] == '0':
            ext = 'mkv'
        ffmpeg_mapped_args.append("-map")
        ffmpeg_mapped_args.append(f"0:{channel['id']}")
        ffmpeg_mapped_args.append(f"{channel['name']}.{ext}")


# OBS callbacks
def on_event(event):
    global recording_dir, recording_output, hostname, port, password, channel_settings, enabled

    if enabled is False:
        return

    if event == obs.OBS_FRONTEND_EVENT_RECORDING_STARTED:
        # Make sure we grab all the data we need to demux later
        debug_print("recording started")
        client = obswebsocket.obsws(hostname, port, password)
        client.connect()
        recording_folder = client.call(obswebsocket.requests.GetRecordingFolder())
        recording_status = client.call(obswebsocket.requests.GetRecordingStatus())
        recording_dir = recording_folder.getRecFolder()
        recording_output = recording_status.getRecordingFilename()
        client.disconnect()
        debug_print("recording dir", recording_dir, "recording file:", recording_output)
    elif event == obs.OBS_FRONTEND_EVENT_RECORDING_STOPPED:
        # create our recording output
        debug_print("stopped recording for file:", recording_output)
        thread = MyDemuxThread()
        thread.daemon = True
        thread.start()


def script_defaults(settings):
    debug_print("Loaded defaults.")

    obs.obs_data_set_default_bool(settings, "enabled", enabled)
    obs.obs_data_set_default_bool(settings, "debug_mode", debug_mode)
    obs.obs_data_set_default_bool(settings, "delete_source", delete_source)
    obs.obs_data_set_default_string(settings, "wshostname", hostname)
    obs.obs_data_set_default_int(settings, "wsport", 4444)
    obs.obs_data_set_default_string(settings, "wspass", password)

    obs_channel = obs.obs_data_get_array(settings, "channel_list")
    if obs.obs_data_array_count(obs_channel) <= 0:
        obs_array = obs.obs_data_array_create()
        item = obs.obs_data_create()
        obs.obs_data_set_string(item, "value", "0|Video")
        obs.obs_data_array_push_back(obs_array, item)
        obs.obs_data_release(item)
        item = obs.obs_data_create()
        obs.obs_data_set_string(item, "value", "1|DefaultAudio")
        obs.obs_data_array_push_back(obs_array, item)
        obs.obs_data_release(item)
        obs.obs_data_set_array(settings, "channel_list", obs_array)
        obs.obs_data_array_release(obs_array)

    obs.obs_data_array_release(obs_channel)


def script_update(settings):
    global debug_mode, hostname, port, password, channel_settings, delete_source, enabled
    debug_print("Updated properties")

    enabled = obs.obs_data_get_bool(settings, "enabled")
    debug_mode = obs.obs_data_get_bool(settings, "debug_mode")
    delete_source = obs.obs_data_get_bool(settings, "delete_source")
    hostname = obs.obs_data_get_string(settings, "wshostname")
    port = obs.obs_data_get_int(settings, "wsport")
    password = obs.obs_data_get_string(settings, "wspass")
    obs_channel = obs.obs_data_get_array(settings, "channel_list")
    num_channel = obs.obs_data_array_count(obs_channel)
    channel_settings = []
    for i in range(num_channel):  # Convert C array to Python list
        message_object = obs.obs_data_array_item(obs_channel, i)
        channel_settings.append(obs.obs_data_get_string(message_object, "value"))
    obs.obs_data_array_release(obs_channel)
    generate_output_params()


def script_load(settings):
    debug_print("Loaded script")
    obs.obs_frontend_add_event_callback(on_event)


def script_description():
    return "<b>OBS Recording Demuxer</b>" \
           "<hr>Adds the ability to demux recording channels.<br/>" \
           "Channel format is \"{track id}|{output filename}\"<br/>" \
           "Channel can also just be \"{track id}\" in which case the output file name will be the {track " \
           "id}<br/><br/>" \
           "Create by Christopher Torres, © 2022" \
           "</hr>"


def script_properties():  # ui
    debug_print("Loaded properties")
    props = obs.obs_properties_create()
    obs.obs_properties_add_text(props, "wshostname", "Websocket hostname", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_int(props, "wsport", "Websocket port", 1024, 65535, 1)
    obs.obs_properties_add_text(props, "wspass", "Websocket password", obs.OBS_TEXT_PASSWORD)
    obs.obs_properties_add_editable_list(props, "channel_list", "Channels to demux",
                                         obs.OBS_EDITABLE_LIST_TYPE_STRINGS, "", "")
    obs.obs_properties_add_bool(props, "enabled", "Enabled")
    obs.obs_properties_add_bool(props, "delete_source", "Delete source recording file")
    obs.obs_properties_add_bool(props, "debug_mode", "Debug Mode")
    return props
