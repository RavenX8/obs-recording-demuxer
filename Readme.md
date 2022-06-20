# OBS Recording Demuxer

## Requirements

[obs-websocket], [obs-websocket-py] and [ffmpeg]

## Setting 

To select what channels from the recording to demux add each channel to the "Channels to demux" setting

Format for each entry is `<channel id>|<out filename>`

Channel ID 0 is always the video channel 

Channel ID 1-6 are the audio channels in relation to Advanced Audio Properties -> Tracks

[obs-websocket]: https://obsproject.com/forum/resources/obs-websocket-remote-control-obs-studio-from-websockets.466/
[obs-websocket-py]: https://github.com/Elektordi/obs-websocket-py
[ffmpeg]: https://ffmpeg.org/
