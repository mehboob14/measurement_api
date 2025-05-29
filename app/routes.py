from flask import Flask, Blueprint, request, jsonify, render_template
from .llm_utils import extract_measurements
import os

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/process-images', methods=['POST'])
def process_images():
    image1 = request.files.get('front_image')
    image2 = request.files.get('side_image')
    height = request.form.get('height')

    if not all([image1, image2, height]):
        return jsonify({'error': 'Missing data'}), 400

    result = extract_measurements(image1, image2, height)
    
    return jsonify({'result': result})
