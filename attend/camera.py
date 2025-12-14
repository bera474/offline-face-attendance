import cv2


class Camera:
    def __init__(self, index: int = 0):
        self.index = index
        self.cap = None

    def open(self) -> bool:
        self.cap = cv2.VideoCapture(self.index)
        return self.cap.isOpened()

    def read(self):
        ok, frame = self.cap.read()
        return ok, frame

    def release(self):
        if self.cap:
            self.cap.release()
            self.cap = None

    def set_prop(self, prop_id: int, value):
        if self.cap:
            self.cap.set(prop_id, value)