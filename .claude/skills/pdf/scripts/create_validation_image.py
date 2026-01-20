import json
import sys
from PIL import Image, ImageDraw


# Creates a validation image showing bounding boxes overlaid on the original image.
# Red rectangles mark entry fields, blue rectangles mark labels.


def create_validation_image(page_number, fields_json_path, input_image_path, output_image_path):
    """Create a validation image with bounding boxes drawn on it."""

    # Load the fields.json
    with open(fields_json_path, 'r') as f:
        fields_data = json.load(f)

    # Open the input image
    image = Image.open(input_image_path)
    draw = ImageDraw.Draw(image)

    # Filter fields for this page
    page_fields = [f for f in fields_data["form_fields"] if f["page_number"] == page_number]

    # Draw bounding boxes
    entry_count = 0
    label_count = 0

    for field in page_fields:
        # Draw entry bounding box in red
        entry_box = field["entry_bounding_box"]
        draw.rectangle(
            [(entry_box[0], entry_box[1]), (entry_box[2], entry_box[3])],
            outline="red",
            width=2
        )
        entry_count += 1

        # Draw label bounding box in blue
        label_box = field["label_bounding_box"]
        draw.rectangle(
            [(label_box[0], label_box[1]), (label_box[2], label_box[3])],
            outline="blue",
            width=2
        )
        label_count += 1

    # Save the output image
    image.save(output_image_path)
    print(f"Created validation image with {entry_count} entry boxes (red) and {label_count} label boxes (blue)")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: create_validation_image.py [page_number] [fields.json] [input_image] [output_image]")
        sys.exit(1)

    page_number = int(sys.argv[1])
    fields_json_path = sys.argv[2]
    input_image_path = sys.argv[3]
    output_image_path = sys.argv[4]

    create_validation_image(page_number, fields_json_path, input_image_path, output_image_path)
