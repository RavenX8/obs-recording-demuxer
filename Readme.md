# OBS Recording Demuxer

## Requirements

[obs-websocket] and [ffmpeg]

## Setting 

To select what channels from the recording to demux add each channel to the "Channels to demux" setting

Format for each entry is `<channel id>|<out filename>`

Channel ID 0 is always the video channel 

Channel ID 1-6 are the audio channels in relation to Advanced Audio Properties -> Tracks

[obs-websocket]: https://obsproject.com/forum/resources/obs-websocket-remote-control-obs-studio-from-websockets.466/
[ffmpeg]: https://ffmpeg.org/