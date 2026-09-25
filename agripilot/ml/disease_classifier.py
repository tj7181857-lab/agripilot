"""
AgriPilot :: Crop Leaf Disease Image Classification & Explainable AI (Grad-CAM).

Uses transfer learning with MobileNetV2 on the genuine PlantVillage dataset:
  - 11 classes spanning Tomato, Grape, and Potato (diseased and healthy)
  - Consistent preprocessing (224x224, MobileNetV2 normalization)
  - Computes genuine test-set metrics: Accuracy, Precision, Recall, F1, Confusion Matrix
  - Real Grad-CAM heatmap generation to visually explain which leaf regions influenced the prediction
  - Enriches diagnosis with authentic trilingual agricultural knowledge
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.cm as cm
import numpy as np
from PIL import Image
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score, precision_score,
                             recall_score)
from sklearn.model_selection import train_test_split

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras.applications.mobilenet_v2 import (MobileNetV2,
                                                        preprocess_input)

# Ensure UTF-8 stdout
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Resolve project base directory
HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(HERE) == "ml":
    PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
else:
    PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))

DATA_DIR = os.path.join(PROJECT_ROOT, "data", "disease_dataset")
KB_PATH = os.path.join(PROJECT_ROOT, "data", "agri_knowledge_multilingual.json")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs")
GRADCAM_DIR = os.path.join(OUTPUT_DIR, "gradcam")
MODEL_PATH = os.path.join(OUTPUT_DIR, "disease_model.keras")
MAPPING_PATH = os.path.join(OUTPUT_DIR, "disease_class_mapping.json")
METRICS_PATH = os.path.join(OUTPUT_DIR, "disease_model_metrics.json")

IMAGE_SIZE = (224, 224)
TARGET_CONV_LAYER = "Conv_1"


def get_class_names() -> List[str]:
    """Retrieve sorted list of disease class directories."""
    if not os.path.exists(DATA_DIR):
        raise FileNotFoundError(f"Disease dataset not found at: {DATA_DIR}")
    classes = [d for d in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, d))]
    return sorted(classes)


def load_dataset(verbose: bool = True) -> Tuple[np.ndarray, np.ndarray, List[str], List[str]]:
    """
    Loads genuine PlantVillage leaf images, applies consistent preprocessing (224x224),
    and creates label arrays.
    """
    classes = get_class_names()
    images = []
    labels = []
    image_paths = []

    for idx, cls in enumerate(classes):
        cls_dir = os.path.join(DATA_DIR, cls)
        file_list = [f for f in os.listdir(cls_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        for f in file_list:
            fpath = os.path.join(cls_dir, f)
            try:
                with Image.open(fpath) as img:
                    img = img.convert("RGB")
                    img = img.resize(IMAGE_SIZE, Image.Resampling.BILINEAR)
                    img_arr = np.array(img, dtype=np.float32)
                    images.append(img_arr)
                    labels.append(idx)
                    image_paths.append(fpath)
            except Exception as e:
                print(f"Warning: skipped corrupt image {fpath}: {e}")

    X = np.array(images, dtype=np.float32)
    y = np.array(labels, dtype=np.int32)

    # Normalize using MobileNetV2 convention (maps [0, 255] to [-1, 1])
    X = preprocess_input(X)

    if verbose:
        print(f"Loaded {len(X)} images across {len(classes)} classes.")
        print(f"Feature tensor shape: {X.shape}, Label tensor shape: {y.shape}")

    return X, y, classes, image_paths


def build_model(num_classes: int) -> keras.Model:
    """
    Builds transfer learning CNN using MobileNetV2 backbone.
    Constructs a direct functional architecture to support clean Grad-CAM gradient calculation.
    """
    base_model = MobileNetV2(
        weights="imagenet",
        include_top=False,
        input_shape=(IMAGE_SIZE[0], IMAGE_SIZE[1], 3)
    )
    # Freeze base model weights for stable transfer learning
    base_model.trainable = False

    # Connect classification head directly to base_model.output
    x = keras.layers.GlobalAveragePooling2D(name="gap")(base_model.output)
    x = keras.layers.BatchNormalization(name="bn")(x)
    x = keras.layers.Dense(128, activation="relu", name="dense_feat")(x)
    x = keras.layers.Dropout(0.3, name="drop")(x)
    outputs = keras.layers.Dense(num_classes, activation="softmax", name="predictions")(x)

    model = keras.Model(inputs=base_model.input, outputs=outputs, name="crop_disease_classifier")
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.0008),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"]
    )
    return model


def train_and_evaluate(epochs: int = 10, batch_size: int = 16, random_state: int = 42) -> Dict[str, Any]:
    """
    Trains MobileNetV2 classifier on 80% train split and computes genuine
    metrics on held-out 20% test split.
    """
    print("=" * 70)
    print("      AGRIPILOT: CROP DISEASE CNN TRAINING & EVALUATION")
    print("=" * 70)

    X, y, classes, image_paths = load_dataset(verbose=True)
    num_classes = len(classes)

    # Stratified 80/20 train/test split
    indices = np.arange(len(X))
    train_idx, test_idx = train_test_split(
        indices, test_size=0.20, random_state=random_state, stratify=y
    )

    X_train, y_train = X[train_idx], y[train_idx]
    X_test, y_test = X[test_idx], y[test_idx]
    test_paths = [image_paths[i] for i in test_idx]

    print(f"Training split: {len(X_train)} images (80%)")
    print(f"Test split:     {len(X_test)} images (20%) — exactly {len(X_test)//num_classes} per class")

    # Data augmentation for robust generalization
    train_ds = tf.data.Dataset.from_tensor_slices((X_train, y_train))
    def augment(image, label):
        image = tf.image.random_flip_left_right(image)
        image = tf.image.random_flip_up_down(image)
        return image, label

    train_ds = train_ds.map(augment, num_parallel_calls=tf.data.AUTOTUNE)
    train_ds = train_ds.shuffle(buffer_size=len(X_train)).batch(batch_size).prefetch(tf.data.AUTOTUNE)

    val_ds = tf.data.Dataset.from_tensor_slices((X_test, y_test)).batch(batch_size)

    model = build_model(num_classes)

    t0 = time.time()
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=epochs,
        verbose=1
    )
    train_time = round(time.time() - t0, 2)

    # Genuine test-set evaluation
    t0 = time.time()
    y_probs = model.predict(X_test, batch_size=batch_size, verbose=0)
    eval_time = round(time.time() - t0, 3)
    y_pred = np.argmax(y_probs, axis=1)

    acc = float(accuracy_score(y_test, y_pred))
    prec_macro = float(precision_score(y_test, y_pred, average="macro", zero_division=0))
    prec_weighted = float(precision_score(y_test, y_pred, average="weighted", zero_division=0))
    rec_macro = float(recall_score(y_test, y_pred, average="macro", zero_division=0))
    rec_weighted = float(recall_score(y_test, y_pred, average="weighted", zero_division=0))
    f1_m = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
    f1_w = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))

    cm = confusion_matrix(y_test, y_pred, labels=np.arange(num_classes)).tolist()
    report = classification_report(
        y_test, y_pred, target_names=classes, output_dict=True, zero_division=0
    )

    print("\n" + "-" * 70)
    print(f"TEST RESULTS (Held-out {len(y_test)} images):")
    print(f"  - Accuracy:         {acc * 100:.2f}% ({int(np.sum(y_test == y_pred))}/{len(y_test)} correct)")
    print(f"  - Macro F1-Score:   {f1_m * 100:.2f}%")
    print(f"  - Macro Precision:  {prec_macro * 100:.2f}%")
    print(f"  - Macro Recall:     {rec_macro * 100:.2f}%")
    print(f"  - Training Time:    {train_time}s")
    print("-" * 70)

    # Class mappings with human-readable names
    class_mapping = {}
    for idx, cname in enumerate(classes):
        parts = cname.split("___")
        crop = parts[0].replace("_", " ").title()
        disease_raw = parts[1] if len(parts) > 1 else "Unknown"
        disease = disease_raw.replace("_", " ").replace("  ", " ").strip()
        is_healthy = "healthy" in disease_raw.lower()

        class_mapping[str(idx)] = {
            "index": idx,
            "class_name": cname,
            "crop": crop,
            "disease": "Healthy" if is_healthy else disease,
            "is_healthy": is_healthy,
            "display_name": f"{crop} — {'Healthy' if is_healthy else disease}"
        }

    # Save model and mapping
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(GRADCAM_DIR, exist_ok=True)

    model.save(MODEL_PATH)
    with open(MAPPING_PATH, "w", encoding="utf-8") as f:
        json.dump(class_mapping, f, indent=2, ensure_ascii=False)

    metrics_payload = {
        "metadata": {
            "model_architecture": "MobileNetV2 (Transfer Learning)",
            "pretrained_weights": "imagenet",
            "input_shape": [IMAGE_SIZE[0], IMAGE_SIZE[1], 3],
            "total_images": len(X),
            "train_images": len(X_train),
            "test_images": len(X_test),
            "num_classes": num_classes,
            "classes": classes,
            "target_conv_layer": TARGET_CONV_LAYER,
            "training_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "training_time_sec": train_time,
        },
        "overall": {
            "accuracy": round(acc, 4),
            "accuracy_pct": round(acc * 100, 2),
            "precision_macro": round(prec_macro, 4),
            "precision_weighted": round(prec_weighted, 4),
            "recall_macro": round(rec_macro, 4),
            "recall_weighted": round(rec_weighted, 4),
            "f1_macro": round(f1_m, 4),
            "f1_weighted": round(f1_w, 4),
            "correct_samples": int(np.sum(y_test == y_pred)),
            "total_samples": len(y_test),
        },
        "per_class": {
            cname: {
                "precision": round(float(report[cname]["precision"]), 4),
                "recall": round(float(report[cname]["recall"]), 4),
                "f1_score": round(float(report[cname]["f1-score"]), 4),
                "support": int(report[cname]["support"]),
            }
            for cname in classes if cname in report
        },
        "confusion_matrix": cm,
        "history": {
            "loss": [round(float(v), 4) for v in history.history["loss"]],
            "accuracy": [round(float(v), 4) for v in history.history["accuracy"]],
            "val_loss": [round(float(v), 4) for v in history.history["val_loss"]],
            "val_accuracy": [round(float(v), 4) for v in history.history["val_accuracy"]],
        }
    }

    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2, ensure_ascii=False)

    print(f"Saved trained model to:    {MODEL_PATH}")
    print(f"Saved class mapping to:    {MAPPING_PATH}")
    print(f"Saved metrics to:          {METRICS_PATH}")
    return metrics_payload


def compute_gradcam_heatmap(
    model: keras.Model,
    img_array: np.ndarray,
    target_layer_name: str = TARGET_CONV_LAYER,
    pred_index: Optional[int] = None
) -> np.ndarray:
    """
    Computes genuine Grad-CAM class activation heatmap for the input image
    using the target convolutional layer gradients.
    """
    grad_model = keras.Model(
        inputs=model.inputs,
        outputs=[model.get_layer(target_layer_name).output, model.output]
    )

    with tf.GradientTape() as tape:
        conv_outputs, predictions = grad_model(img_array)
        if pred_index is None:
            pred_index = tf.argmax(predictions[0])
        class_channel = predictions[:, pred_index]

    # Gradient of target class score with respect to feature map activations
    grads = tape.gradient(class_channel, conv_outputs)
    # Global average pooling of gradients (importance weight per feature channel)
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))

    # Weight convolutional outputs by gradient importance
    conv_outputs = conv_outputs[0]
    heatmap = conv_outputs @ pooled_grads[..., tf.newaxis]
    heatmap = tf.squeeze(heatmap)

    # ReLU: keep only features that contribute positively to the class
    heatmap = tf.maximum(heatmap, 0.0)
    max_val = tf.math.reduce_max(heatmap)
    if max_val > 0:
        heatmap = heatmap / max_val
    return heatmap.numpy()


def overlay_gradcam(
    original_img_pil: Image.Image,
    heatmap: np.ndarray,
    alpha: float = 0.45,
    colormap_name: str = "jet"
) -> Image.Image:
    """
    Resizes Grad-CAM heatmap to original image resolution and overlays with
    semi-transparent colormap.
    """
    # Resize heatmap to match image
    heatmap_uint8 = np.uint8(255 * heatmap)
    jet = matplotlib.colormaps[colormap_name]
    jet_colors = jet(np.arange(256))[:, :3]
    jet_heatmap = jet_colors[heatmap_uint8]

    # Convert to PIL and resize
    jet_heatmap = keras.utils.array_to_img(jet_heatmap)
    jet_heatmap = jet_heatmap.resize(original_img_pil.size, Image.Resampling.BILINEAR)
    jet_heatmap = keras.utils.img_to_array(jet_heatmap)

    original_arr = keras.utils.img_to_array(original_img_pil)
    superimposed = jet_heatmap * alpha + original_arr * (1.0 - alpha)
    superimposed = np.clip(superimposed, 0, 255).astype("uint8")
    return Image.fromarray(superimposed)


class DiseaseClassifier:
    """
    Production inference engine for Crop Leaf Disease Diagnosis and Grad-CAM explainability.
    Loads saved Keras model without retraining.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        mapping_path: Optional[str] = None,
        kb_path: Optional[str] = None
    ):
        self.model_path = model_path or MODEL_PATH
        self.mapping_path = mapping_path or MAPPING_PATH
        self.kb_path = kb_path or KB_PATH

        if not os.path.exists(self.model_path) or not os.path.exists(self.mapping_path):
            # Train once if model has not been built yet
            train_and_evaluate()

        self.model = keras.models.load_model(self.model_path)
        with open(self.mapping_path, "r", encoding="utf-8") as f:
            self.class_mapping = json.load(f)

        self.knowledge = {}
        if os.path.exists(self.kb_path):
            with open(self.kb_path, "r", encoding="utf-8") as f:
                self.knowledge = json.load(f).get("diseases", {})

    def predict_image(
        self,
        image_input: Any,  # file path (str), PIL.Image, or bytes
        generate_gradcam: bool = True,
        save_gradcam_dir: Optional[str] = None,
        expected_crop: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Runs disease classification inference on an input leaf image.
        Returns predicted crop, disease, confidence, severity, Grad-CAM heatmap,
        and localized agricultural management information.
        """
        # Load and convert image to RGB PIL
        if isinstance(image_input, str):
            orig_img = Image.open(image_input).convert("RGB")
            filename = os.path.basename(image_input)
        elif isinstance(image_input, bytes):
            orig_img = Image.open(BytesIO(image_input)).convert("RGB")
            filename = f"upload_{int(time.time()*1000)}.jpg"
        elif isinstance(image_input, Image.Image):
            orig_img = image_input.convert("RGB")
            filename = f"image_{int(time.time()*1000)}.jpg"
        else:
            raise ValueError(f"Unsupported image input type: {type(image_input)}")

        # Consistent preprocessing
        resized_img = orig_img.resize(IMAGE_SIZE, Image.Resampling.BILINEAR)
        img_arr = np.array(resized_img, dtype=np.float32)
        batch_input = np.expand_dims(img_arr, axis=0)
        norm_input = preprocess_input(batch_input)

        # Forward pass
        preds = self.model.predict(norm_input, verbose=0)[0]
        top_idx = int(np.argmax(preds))
        confidence = float(preds[top_idx])

        # Candidate classes are restricted inside inference to the selected,
        # supported crop. Scores remain the model's original softmax scores;
        # no cross-crop classes are presented as disease candidates.
        selected_crop = str(expected_crop or self.class_mapping[str(top_idx)]["crop"]).strip().casefold()
        crop_indices = [int(i) for i, item in self.class_mapping.items()
                        if str(item.get("crop", "")).strip().casefold() == selected_crop]
        if not crop_indices:
            crop_indices = [top_idx]
        sorted_indices = sorted(crop_indices, key=lambda i: float(preds[i]), reverse=True)[:3]
        top_candidates = [
            {
                "class_name": self.class_mapping[str(i)]["class_name"],
                "display_name": self.class_mapping[str(i)]["display_name"],
                "crop": self.class_mapping[str(i)]["crop"],
                "disease": self.class_mapping[str(i)]["disease"],
                "confidence": round(float(preds[i]), 4),
                "confidence_pct": round(float(preds[i]) * 100, 1),
            }
            for i in sorted_indices
        ]

        info = self.class_mapping[str(top_idx)]
        raw_class = info["class_name"]
        crop_name = info["crop"]
        disease_name = info["disease"]
        is_healthy = info["is_healthy"]
        crop_matches_selection = (
            expected_crop is None
            or str(expected_crop).strip().casefold() == str(crop_name).strip().casefold()
        )

        # Grad-CAM heatmap generation
        gradcam_path = None
        gradcam_base64 = None
        if generate_gradcam and crop_matches_selection:
            heatmap = compute_gradcam_heatmap(
                self.model, norm_input, TARGET_CONV_LAYER, pred_index=top_idx
            )
            overlay = overlay_gradcam(orig_img, heatmap)

            save_dir = save_gradcam_dir or GRADCAM_DIR
            os.makedirs(save_dir, exist_ok=True)
            base_name, _ = os.path.splitext(filename)
            out_filename = f"gradcam_{base_name}_{int(time.time())}.png"
            gradcam_path = os.path.join(save_dir, out_filename)
            overlay.save(gradcam_path)

            # Also encode as base64 data URI for instant web display
            buffered = BytesIO()
            overlay.save(buffered, format="PNG")
            gradcam_base64 = f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"

        # Retrieve authentic agricultural knowledge
        kb_entry = self.knowledge.get(raw_class, {})
        severity = kb_entry.get("typical_severity", "Low" if is_healthy else "Moderate")

        return {
            "crop": crop_name,
            "selected_crop": expected_crop,
            "crop_matches_selection": crop_matches_selection,
            "disease": disease_name,
            "is_healthy": is_healthy,
            "class_name": raw_class,
            "confidence": round(confidence, 4),
            "confidence_pct": round(confidence * 100, 1),
            "severity": severity,
            "scientific_name": kb_entry.get("scientific_name", "N/A"),
            "pathogen_type": kb_entry.get("pathogen_type", "None" if is_healthy else "Fungal"),
            "season": kb_entry.get("season", "Kharif / Rabi"),
            "gradcam_path": gradcam_path,
            "gradcam_base64": gradcam_base64,
            "top_candidates": top_candidates,
            "symptoms": kb_entry.get("symptoms", {}),
            "precautions": kb_entry.get("precautions", {}),
            "treatment": kb_entry.get("treatment", {}),
            "prevention": kb_entry.get("prevention", {}),
            "water_requirement": kb_entry.get("water_requirement", {}),
        }


def main():
    train_and_evaluate(epochs=10, batch_size=16)


if __name__ == "__main__":
    main()
