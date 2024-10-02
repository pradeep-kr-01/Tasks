from flask import Flask, render_template, request, jsonify
import base64
import boto3
from io import BytesIO
import cv2
import numpy as np
import os
from datetime import datetime

app = Flask(__name__)

# AWS S3 Configuration
AWS_ACCESS_KEY = 'AKIAYPQBYIT6ZUAQKY7V'  # Replace with your AWS access key
AWS_SECRET_KEY = 'kg7aevejaohVFxhtWC4IhSvo5iqKUXa1dmXz5imV'  # Replace with your AWS secret key
AWS_REGION = 'ap-south-1'          # Replace with your AWS region (e.g., 'us-west-2')
S3_BUCKET_NAME = 'mydatabasetask'  # Replace with your S3 bucket name

# Initialize the S3 client
s3_client = boto3.client('s3', 
                         aws_access_key_id=AWS_ACCESS_KEY,
                         aws_secret_access_key=AWS_SECRET_KEY,
                         region_name=AWS_REGION)

# Serve the frontend HTML file
@app.route('/')
def index():
    return render_template('index.html')  # Serves the index.html from /templates folder

# Route to save image to S3
@app.route('/save_image', methods=['POST'])
def save_image():
    data = request.get_json()
    image_data = data['image']
    
    # Remove the 'data:image/png;base64,' part of the image string
    image_data = image_data.split(',')[1]
    
    # Decode the image
    image = base64.b64decode(image_data)
    
    # Convert to BytesIO for uploading to S3
    image_io = BytesIO(image)
    
    # Generate a unique filename based on timestamp
    filename = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    
    # Upload to S3
    try:
        s3_client.upload_fileobj(
            image_io, 
            S3_BUCKET_NAME, 
            filename,
            ExtraArgs={'ContentType': 'image/png'}
        )
        return jsonify({"message": "Image saved to S3 successfully!"}), 200
    except Exception as e:
        print(f"Error uploading to S3: {e}")
        return jsonify({"message": "Failed to save image to S3."}), 500

# Route to capture image with filters
@app.route('/capture', methods=['POST'])
def capture_image():
    filter_type = request.get_json().get('filter')
    
    # Start video capture from the webcam
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        return jsonify({"message": "Could not open webcam."}), 500

    # Capture the frame
    ret, frame = cap.read()

    # Apply the chosen filter
    if filter_type == 'grayscale':
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    elif filter_type == 'sepia':
        kernel = np.array([[0.272, 0.534, 0.131],
                           [0.349, 0.686, 0.168],
                           [0.393, 0.769, 0.189]])
        frame = cv2.transform(frame, kernel)
    elif filter_type == 'invert':
        frame = cv2.bitwise_not(frame)
    elif filter_type == 'blur':
        frame = cv2.GaussianBlur(frame, (15, 15), 0)

    # Encode the frame as a PNG image
    _, buffer = cv2.imencode('.png', frame)
    image_data = base64.b64encode(buffer).decode('utf-8')

    # Stop video capture
    cap.release()

    return jsonify({"image": f"data:image/png;base64,{image_data}"}), 200

# New route to fetch stored images from S3
@app.route('/get_images', methods=['GET'])
def get_images():
    # Fetch the list of images stored in the S3 bucket
    try:
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET_NAME)
        images = []
        
        if 'Contents' in response:
            for obj in response['Contents']:
                image_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{obj['Key']}"
                images.append(image_url)
        
        return jsonify({"images": images}), 200
    except Exception as e:
        print(f"Error fetching images from S3: {e}")
        return jsonify({"message": "Failed to fetch images from S3."}), 500

if __name__ == '__main__':
    # Get the port number from environment variables or default to 5000
    port = int(os.environ.get("PORT", 5500))
    # Bind to 0.0.0.0 to make the app externally accessible on the server
    app.run(host="0.0.0.0", port=port)

