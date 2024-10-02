from flask import Flask, Response, render_template, request
import cv2
import boto3
import numpy as np
import uuid
import os
import tempfile
import platform

app = Flask(__name__)

# AWS S3 configuration
AWS_ACCESS_KEY = 'AKIAYPQBYIT6ZUAQKY7V'  # Replace with your Access Key
AWS_SECRET_KEY = 'kg7aevejaohVFxhtWC4IhSvo5iqKUXa1dmXz5imV'  # Replace with your Secret Key
BUCKET_NAME = 'mydatabasetask'  # Replace with your S3 bucket name

# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY
)

# Check if the app is running locally (i.e., not on a cloud platform)
is_local = platform.system() in ['Linux', 'Darwin', 'Windows']  # Adjust for other platforms if needed

if is_local:
    # Initialize video capture (for local systems only)
    video_capture = cv2.VideoCapture(0)
    
    if not video_capture.isOpened():
        print("Camera is not accessible. Running in simulation mode.")
        video_capture = None
else:
    print("Running on a cloud platform, camera access disabled.")
    video_capture = None

def apply_filter(frame, filter_type):
    """Apply selected filter to the video frame."""
    if filter_type == 'grayscale':
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    elif filter_type == 'invert':
        return cv2.bitwise_not(frame)  # Invert colors
    return frame

def generate_frames(filter_type):
    """Generate video frames with applied filter."""
    if video_capture is None:
        # In cloud environments, serve a static image or placeholder video
        placeholder_image = cv2.imread('static/placeholder.jpg')  # Add a placeholder image in static/
        while True:
            ret, buffer = cv2.imencode('.jpg', placeholder_image)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    else:
        while True:
            success, frame = video_capture.read()
            if not success:
                break
            frame = apply_filter(frame, filter_type)
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def index():
    """Render the main index page."""
    return render_template('index.html')

@app.route('/video_feed/<filter_type>')
def video_feed(filter_type):
    """Stream video feed with the specified filter."""
    return Response(generate_frames(filter_type), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/capture', methods=['POST'])
def capture():
    """Capture an image and upload it to S3."""
    filter_type = request.form['filter_type']
    if video_capture is not None:
        success, frame = video_capture.read()
        if success:
            frame = apply_filter(frame, filter_type)
            filename = f"{uuid.uuid4()}.jpg"
            
            # Use tempfile to create a temporary file path
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                temp_file_path = temp_file.name
                cv2.imwrite(temp_file_path, frame)

            try:
                # Upload the image to S3 after closing the tempfile
                s3_client.upload_file(temp_file_path, BUCKET_NAME, filename)
                os.remove(temp_file_path)  # Clean up temporary file
                return {'message': 'Image captured and uploaded to S3', 'filename': filename}, 200
            except Exception as e:
                return {'error': f'Failed to upload to S3: {str(e)}'}, 500
        return {'error': 'Failed to capture image'}, 500
    else:
        return {'error': 'Camera is not accessible in this environment'}, 500

@app.route('/open_camera', methods=['GET'])
def open_camera():
    """Open the camera (for internal use)."""
    if video_capture is None:
        return {'error': 'Camera is not accessible'}, 500
    return {'message': 'Camera is opened'}, 200

if __name__ == '__main__':
    # Get the port number from environment variables or default to 5000
    port = int(os.environ.get("PORT", 5500))
    # Bind to 0.0.0.0 to make the app externally accessible on the server
    app.run(host="0.0.0.0", port=port)
