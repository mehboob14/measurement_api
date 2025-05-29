import re
from collections import defaultdict
import statistics
import base64
import mimetypes
from dotenv import load_dotenv
import os
from openai import OpenAI, OpenAIError
from flask import Blueprint, request, jsonify

llm_bp = Blueprint('llm_bp', __name__)

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise EnvironmentError("OPENAI_API_KEY not found in .env")

client = OpenAI(api_key=api_key)


Models = [
    "gpt-4.1",
    "gpt-4.1-2025-04-14",
]

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def parse_markdown_table(markdown):
    rows = [line.strip() for line in markdown.strip().splitlines() if line.strip()]
    measurements = {}
    for row in rows:
        if '|' in row and not row.startswith('| Measurement'):
            parts = [p.strip() for p in row.strip('|').split('|')]
            if len(parts) == 2:
                name, value = parts
                try:
                    val = float(re.sub(r'[^\d\.]', '', value))
                    measurements[name.lower()] = val
                except ValueError:
                    continue
    return measurements

desired_order = [
    "Upper bust", "Bust", "Under bust", "Waist circumference", "High hip",
    "Low hip", "Thigh circumference", "Arm circumference", "Wrist circumference",
    "Back shoulder width", "Shoulder width", "Arm length", "Waist to hip",
    "Waist to knee", "Waist to floor"
]

calibration_percentages = {
    "upper bust": 1.7, "bust": 1.8, "under bust": 2.5, "waist circumference": 2.95,
    "high hip": 7.23, "low hip": -0.4, "thigh circumference": -6.2598, "arm circumference": -7.1,
    "wrist circumference": -0.24, "back shoulder width": 10.71, "shoulder width": 37.53,
    "arm length": -0.22, "waist to hip": 23.19, "waist to knee": 17.43, "waist to floor": 4.43,
}

@llm_bp.route('/generate-measurements', methods=['POST'])
def extract_measurements():
    print(request.files)
    print(request.form)
    front_image = request.files.get('front_image')
    side_image = request.files.get('side_image')
    height = request.form.get('height')

    if not front_image or not side_image or not height:
        return jsonify({"error": "Missing front_image, side_image or height"}), 400

    temp_dir = os.path.join(os.getcwd(), "static", "temp")
    os.makedirs(temp_dir, exist_ok=True)

    front_path = os.path.join(temp_dir, front_image.filename)
    side_path = os.path.join(temp_dir, side_image.filename)

    front_image.save(front_path)
    side_image.save(side_path)

    try:
        image_paths = [front_path, side_path]
        image_contents = []
        for path in image_paths:
            mime_type, _ = mimetypes.guess_type(path)
            base64_img = encode_image(path)
            image_contents.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{base64_img}",
                    "detail": "high"
                }
            })

        prompt = f"""
        You are a master tailor with vision-based anthropometry skills.
        Inputs:
        - Two full-body images of the subject: front view and side view.
        - Subject posture: Standing straight, arms relaxed.
        - Known subject height: {height} inches.
        Use both images to visually estimate and return measurements as a Markdown table.
        Measurements:
        - Upper bust, Bust, Under bust, Waist circumference, High hip, Low hip,
          Thigh circumference, Arm circumference, Wrist circumference,
          Back shoulder width, Shoulder width, Arm length, Waist to hip,
          Waist to knee, Waist to floor.
        """

        all_measurements = defaultdict(list)
        for m in Models:
            response = client.chat.completions.create(
                model=m,
                messages=[{
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}] + image_contents
                }],
                temperature=0.1,
                max_tokens=800,
            )
            result = response.choices[0].message.content.strip()
            model_measurements = parse_markdown_table(result)
            for k, v in model_measurements.items():
                all_measurements[k].append(v)

        output = {}
        for k in desired_order:
            k_lc = k.lower()
            if k_lc in all_measurements:
                values = all_measurements[k_lc]
                avg = round(statistics.mean(values) * 4) / 4
                calibrated = avg + (avg * (calibration_percentages[k_lc] / 100))
                output[k] = round(calibrated, 2)

    finally:
        if os.path.exists(front_path):
            os.remove(front_path)
        if os.path.exists(side_path):
            os.remove(side_path)

    return jsonify({"measurements": output})
