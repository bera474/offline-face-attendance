import numpy as np
import cv2
from .config import CFG

# Try to import insightface, fallback to OpenCV cascade if unavailable
try:
    from insightface.app import FaceAnalysis
    HAS_INSIGHTFACE = True
except ImportError:
    HAS_INSIGHTFACE = False
    print("[embeddings] InsightFace not available, using OpenCV cascade classifier")


class Embedder:
    def __init__(self, model_name: str | None = None, det_size=(640, 640), ctx_id=0):
        self.model_name = model_name or CFG.MODEL_NAME
        self.det_size = det_size
        self.use_insightface = HAS_INSIGHTFACE

        if self.use_insightface:
            try:
                self.app = FaceAnalysis(name=self.model_name)
                self.app.prepare(ctx_id=ctx_id, det_size=self.det_size)
            except Exception as e:
                print(f"[embeddings] Failed to load InsightFace: {e}")
                self.use_insightface = False
                self._init_cascade()
        else:
            self._init_cascade()

    def _init_cascade(self):
        """Initialize OpenCV cascade classifier as fallback"""
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.cascade = cv2.CascadeClassifier(cascade_path)

    def detect_and_embed(self, frame_bgr):
        """
        Returns list of dicts: {bbox: (l,t,r,b), kps: ndarray(5,2), embedding: ndarray(512)}
        """
        if self.use_insightface:
            return self._detect_and_embed_insightface(frame_bgr)
        else:
            return self._detect_and_embed_cascade(frame_bgr)

    def _detect_and_embed_insightface(self, frame_bgr):
        """Use InsightFace for detection and embedding"""
        try:
            faces = self.app.get(frame_bgr)
            out = []
            for f in faces:
                box = f.bbox.astype(int)
                bbox = (box[0], box[1], box[2], box[3])

                out.append({
                    "bbox": bbox,
                    "kps": f.kps,
                    "embedding": f.embedding.astype(np.float32),
                    "landmark_3d_68": f.landmark_3d_68 if hasattr(f, "landmark_3d_68") else None,
                })
            return out
        except Exception as e:
            print(f"[embeddings] InsightFace error: {e}")
            return []

    def _detect_and_embed_cascade(self, frame_bgr):
        """Fallback: Use OpenCV cascade with dummy embeddings"""
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        faces = self.cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

        out = []
        for (x, y, w, h) in faces:
            bbox = (int(x), int(y), int(x+w), int(y+h))

            # Generate dummy embedding from face region
            face_roi = frame_bgr[y:y+h, x:x+w]
            embedding = self._generate_dummy_embedding(face_roi)

            out.append({
                "bbox": bbox,
                "kps": np.array([[x+w/4, y+h/4], [x+3*w/4, y+h/4],
                               [x+w/2, y+h/2], [x+w/4, y+3*h/4],
                               [x+3*w/4, y+3*h/4]], dtype=np.float32),
                "embedding": embedding,
                "landmark_3d_68": None,
            })
        return out

    def _generate_dummy_embedding(self, face_roi):
        """Generate a simple deterministic embedding from face region"""
        # Resize to 64x64 for consistency
        resized = cv2.resize(face_roi, (64, 64))
        # Create embedding from flattened image
        flat = resized.flatten().astype(np.float32) / 255.0
        # Pad/truncate to 512D
        embedding = np.zeros(512, dtype=np.float32)
        embedding[:min(len(flat), 512)] = flat[:512]
        # Normalize
        norm = np.linalg.norm(embedding) + 1e-9
        embedding = embedding / norm
        return embedding