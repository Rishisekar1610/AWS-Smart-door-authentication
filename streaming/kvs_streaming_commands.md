# Camera -> Kinesis Video Stream setup

These commands push a local webcam feed to a Kinesis Video Stream so that
Rekognition Video can analyse it. **Never hard-code your AWS keys here.**
Provide credentials through the environment or an IAM role instead.

> Security note: the original commands embedded an AWS access key and secret
> key inline. Those have been removed. If you ever pasted real keys into a
> command like this, deactivate and rotate them in the IAM console - assume
> they are compromised. Configure credentials with `aws configure` or
> environment variables instead.

## 1. Local RTSP relay (MediaMTX)

```bash
docker run --rm -it -p 8554:8554 -p 8000:8000 -p 8001:8001 \
  bluenviron/mediamtx:latest
```

## 2. Publish the webcam to the RTSP relay (FFmpeg, Windows dshow example)

```bash
ffmpeg -f dshow -framerate 30 -video_size 640x480 \
  -i video="USB2.0 HD UVC WebCam" \
  -vcodec libx264 -preset veryfast \
  -f rtsp -rtsp_transport tcp rtsp://localhost:8554/stream
```

## 3. Run the Kinesis Video Streams Producer SDK container

```bash
docker run -it --rm \
  546150905175.dkr.ecr.us-west-2.amazonaws.com/kinesis-video-producer-sdk-cpp-amazon-linux:latest \
  /bin/bash
```

Inside the container, set the GStreamer paths (adjust to your install):

```bash
export LD_LIBRARY_PATH=/opt/awssdk/amazon-kinesis-video-streams-producer-sdk-cpp/kinesis-video-native-build/downloads/local/lib:$LD_LIBRARY_PATH
export PATH=/opt/awssdk/amazon-kinesis-video-streams-producer-sdk-cpp/kinesis-video-native-build/downloads/local/bin:$PATH
export GST_PLUGIN_PATH=/opt/awssdk/amazon-kinesis-video-streams-producer-sdk-cpp/kinesis-video-native-build/downloads/local/lib:$GST_PLUGIN_PATH
```

## 4. Pipe RTSP -> Kinesis Video Stream (credentials via env, NOT inline)

```bash
export AWS_ACCESS_KEY_ID=<YOUR_ACCESS_KEY>
export AWS_SECRET_ACCESS_KEY=<YOUR_SECRET_KEY>
export AWS_DEFAULT_REGION=us-east-1

gst-launch-1.0 rtspsrc location="rtsp://host.docker.internal:8554/stream" short-header=TRUE \
  ! rtph264depay ! h264parse \
  ! video/x-h264,format=avc,alignment=au \
  ! kvssink stream-name="SmartDoorKVS" storage-size=512 \
      aws-region="us-east-1"
```

> `kvssink` will read credentials from the standard AWS environment variables
> above, so you do not pass `access-key`/`secret-key` on the command line.

## 5. Manage the Rekognition stream processor

```bash
aws rekognition start-stream-processor --name streamProcessorForBlog --region us-east-1
aws rekognition stop-stream-processor  --name streamProcessorForBlog --region us-east-1
```
