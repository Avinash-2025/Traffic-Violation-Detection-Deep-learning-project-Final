import cv2
import numpy as np


class Annotator:
    def __init__(self, config):
        self.config = config
        self.vd_config = config.vd_config
        self.rrl_config = config.rrl_config

        self.color_bbox = (0, 240, 0)
        self.text_font = cv2.FONT_HERSHEY_DUPLEX
        self.text_color = (0, 0, 0)
        self.text_thickness = 1
        self.text_fontscale = 0.5

        self.color_detection_area = (0, 255, 255)
        self.line_thickness_detection_area = 2

        self.rrl_traffic_light_thickness = 2
        self.rrl_bbox_color = (0, 0, 255)
        self.rrl_stopline_color = (0, 0, 255)
        self.rrl_stopline_thickness = 3

        self.hv_text_fontscale = 0.6
        self.hv_text_color = (255, 255, 255)
        self.hv_text_thickness = 2
        self.hv_text_b_color = (0, 0, 220)
        self.hv_text_font = cv2.FONT_HERSHEY_DUPLEX

        self.tr_text_b_color = (180, 0, 180)  # Purple for Triple Riding
        self.tr_bbox_color = (200, 50, 200)

        # Flag to control whether static markup lines (stopline, signal ROI, detection polygon)
        # are burned into the video pixels or rendered dynamically on client canvas
        self.enable_static_markup = getattr(config, "enable_static_markup", False)

    def vehicle_detection(self, img, preds):
        img_new = img.copy()

        # draw detection area only if static markup is explicitly enabled
        if getattr(self, "enable_static_markup", False):
            img_new = self.draw_detection_area(img_new, self.vd_config.detection_area)

        # create bounding boxes
        for obj in preds:
            # add bounding box
            img_new = self.draw_bounding_box(
                img_new, bbox=obj[0:4], color=self.color_bbox
            )
            # add text
            img_new = self.put_text_info(img_new, obj)

        return img_new

    def running_red_light(self, img, preds, violation_list, state=None):
        # create violation vehicle bbox
        img_new = img.copy()
        for obj in preds:
            if obj[6] in violation_list:
                # add bounding box
                img_new = self.draw_bounding_box(
                    img_new, bbox=obj[0:4], color=self.rrl_bbox_color
                )

        # draw stopline & traffic light only if static markup is explicitly enabled
        if getattr(self, "enable_static_markup", False):
            img_new = self.draw_stop_line(img_new, self.rrl_config.stop_line)
            img_new = self.draw_traffic_light(
                img_new, self.rrl_config.traffic_light_area, state
            )
        return img_new

    def helmet_violation(self, img, preds, violation_list):
        img_new = img.copy()
        if violation_list is None or len(violation_list) == 0:
            return img_new
        for obj in preds:
            if obj[6] in violation_list:
                # add helmet violation box
                img_new = self.put_no_helmet(img_new, obj)

        return img_new

    def triple_riding(self, img, preds, violation_list, rider_counts=None):
        img_new = img.copy()
        if violation_list is None or len(violation_list) == 0:
            return img_new

        for obj in preds:
            vid = obj[6]
            if vid in violation_list:
                bbox = obj[0:4]
                cnt = rider_counts.get(vid, 3) if rider_counts else 3
                # draw highlight bounding box
                img_new = self.draw_bounding_box(
                    img_new, bbox=bbox, color=self.tr_bbox_color, thickness=3
                )
                # draw badge
                text_bbox = f"TRIPLE RIDING ({cnt} Riders)"
                text_size, _ = cv2.getTextSize(
                    text_bbox, self.hv_text_font, self.hv_text_fontscale, self.hv_text_thickness
                )
                text_w, text_h = text_size
                bx1, by1 = int(bbox[0]), int(bbox[1])
                cv2.rectangle(
                    img_new,
                    pt1=(bx1, max(0, by1 - text_h - 6)),
                    pt2=(bx1 + text_w + 8, by1),
                    color=self.tr_text_b_color,
                    thickness=cv2.FILLED,
                )
                cv2.putText(
                    img_new,
                    text_bbox,
                    org=(bx1 + 4, max(text_h, by1 - 4)),
                    fontFace=self.hv_text_font,
                    fontScale=self.hv_text_fontscale,
                    color=(255, 255, 255),
                    thickness=self.hv_text_thickness,
                    lineType=cv2.LINE_AA,
                )
        return img_new

    def wrongway_detection(self, img, preds, direction_data, violation):
        img_new = img.copy()

        for obj in preds:
            x_min, y_min, x_max, y_max = obj[0:4]
            object_id = obj[6]

            width = abs(x_max - x_min)
            height = abs(y_max - y_min)

            x_center = x_min + width / 2
            y_center = y_min + height / 2

            if object_id not in direction_data or direction_data[object_id] is None:
                continue

            degree_direction = int(direction_data[object_id])
            rad_direction = np.radians(degree_direction)

            x = (0.2 * np.cos(rad_direction)) * width
            y = (0.2 * np.sin(rad_direction)) * height

            pos1 = (int(x_center - x), int(y_center + y))
            pos2 = (int(x_center), int(y_center))

            color_arrow = (0, 0, 255) if object_id in violation else (0, 255, 0)

            img_new = cv2.arrowedLine(
                img_new,
                pos1,
                pos2,
                color_arrow,
                3,
                cv2.LINE_AA,
                tipLength=0.5,
            )

        return img_new

    def put_no_helmet(self, img0, obj):
        bbox = obj[0:4]

        # add text
        text_bbox = "No Helmet"
        text_size, _ = cv2.getTextSize(
            text_bbox, self.hv_text_font, self.hv_text_fontscale, self.hv_text_thickness
        )
        text_w, text_h = text_size

        img_new = img0.copy()
        img_new = cv2.rectangle(
            img_new,
            pt1=(int(bbox[0]), int(bbox[3])),
            pt2=(int(bbox[0] + text_w), int(bbox[3] + text_h)),
            color=self.hv_text_b_color,
            thickness=cv2.FILLED,
        )

        img_new = cv2.putText(
            img_new,
            text_bbox,
            org=(int(bbox[0]), int(bbox[3] + text_h)),
            fontFace=self.hv_text_font,
            fontScale=self.hv_text_fontscale,
            color=self.hv_text_color,
            thickness=self.hv_text_thickness,
            lineType=cv2.LINE_AA,
        )

        return img_new

    def put_text_info(self, img0, obj):
        bbox = obj[0:4]
        label_idx = obj[5]
        object_id = obj[6]

        # add text
        text_bbox = f"{self.vd_config.classes_names[int(label_idx)]} ({object_id})"
        text_size, _ = cv2.getTextSize(
            text_bbox, self.text_font, self.text_fontscale, self.text_thickness
        )
        text_w, text_h = text_size

        # create background color for text
        img_new = img0.copy()
        img_new = cv2.rectangle(
            img_new,
            pt1=(int(bbox[0]), int(bbox[1])),
            pt2=(int(bbox[0] + text_w), int(bbox[1] - text_h)),
            color=self.color_bbox,
            thickness=cv2.FILLED,
        )
        img_new = cv2.putText(
            img_new,
            text_bbox,
            org=(int(bbox[0]), int(bbox[1])),
            fontFace=self.text_font,
            fontScale=self.text_fontscale,
            color=self.text_color,
            thickness=self.text_thickness,
            lineType=cv2.LINE_AA,
        )
        return img_new

    def draw_bounding_box(self, img0, bbox, color, thickness=2, r=1, d=0.4):

        bbox = [int(p) for p in bbox]
        x1, y1 = bbox[0], bbox[1]
        x2, y2 = bbox[2], bbox[3]
        img = img0.copy()

        width = abs(x2 - x1)
        height = abs(y2 - y1)

        d_x = int(width * d / 2)
        d_y = int(height * d / 2)

        d = 1

        # Top left
        cv2.line(img, (x1 + r, y1), (x1 + r + d_x, y1), color, thickness)
        cv2.line(img, (x1, y1 + r), (x1, y1 + r + d_y), color, thickness)
        cv2.ellipse(img, (x1 + r, y1 + r), (r, r), 180, 0, 90, color, thickness)

        # Top right
        cv2.line(img, (x2 - r, y1), (x2 - r - d_x, y1), color, thickness)
        cv2.line(img, (x2, y1 + r), (x2, y1 + r + d_y), color, thickness)
        cv2.ellipse(img, (x2 - r, y1 + r), (r, r), 270, 0, 90, color, thickness)

        # Bottom left
        cv2.line(img, (x1 + r, y2), (x1 + r + d_x, y2), color, thickness)
        cv2.line(img, (x1, y2 - r), (x1, y2 - r - d_y), color, thickness)
        cv2.ellipse(img, (x1 + r, y2 - r), (r, r), 90, 0, 90, color, thickness)

        # Bottom right
        cv2.line(img, (x2 - r, y2), (x2 - r - d_x, y2), color, thickness)
        cv2.line(img, (x2, y2 - r), (x2, y2 - r - d_y), color, thickness)
        cv2.ellipse(img, (x2 - r, y2 - r), (r, r), 0, 0, 90, color, thickness)

        return img

    def draw_detection_area(self, img0, detection_area):
        if detection_area is None or len(detection_area) < 3:
            return img0

        # Don't draw if full frame
        da_arr = np.array(detection_area, dtype=np.float32)
        if len(detection_area) == 4 and da_arr[:, 0].min() <= 0.05 and da_arr[:, 0].max() >= 0.95 and da_arr[:, 1].min() <= 0.05 and da_arr[:, 1].max() >= 0.95:
            return img0

        height, width = img0.shape[:2]
        pts = np.array([[int(x * width), int(y * height)] for x, y in detection_area], dtype=np.int32)

        # Translucent fill 12% emerald
        overlay = img0.copy()
        cv2.fillPoly(overlay, [pts], (129, 185, 16))  # #10B981 BGR
        img = cv2.addWeighted(overlay, 0.12, img0, 0.88, 0)

        # Dashed border
        cv2.polylines(img, [pts], True, (129, 185, 16), 2, cv2.LINE_AA)
        return img

    def draw_stop_line(self, img0, stop_line):
        if stop_line is None or len(stop_line) < 2:
            return img0
        height, width = img0.shape[:2]
        pts = [[int(x * width), int(y * height)] for x, y in stop_line]
        img = img0.copy()

        red_color = (68, 68, 239)  # #EF4444 BGR

        if len(pts) == 2:
            p1 = tuple(pts[0])
            p2 = tuple(pts[1])

            # Outer soft glow
            cv2.line(img, p1, p2, (40, 40, 160), 6, cv2.LINE_AA)
            # Dashed core line
            dist = int(np.hypot(p2[0] - p1[0], p2[1] - p1[1]))
            dash_len = 16
            gap_len = 10
            for i in range(0, max(1, dist), dash_len + gap_len):
                t1 = i / float(dist)
                t2 = min(1.0, (i + dash_len) / float(dist))
                sp = (int(p1[0] + t1 * (p2[0] - p1[0])), int(p1[1] + t1 * (p2[1] - p1[1])))
                ep = (int(p1[0] + t2 * (p2[0] - p1[0])), int(p1[1] + t2 * (p2[1] - p1[1])))
                cv2.line(img, sp, ep, red_color, 2, cv2.LINE_AA)

            # Circular handles at endpoints
            for pt in (p1, p2):
                cv2.circle(img, pt, 6, (255, 255, 255), -1, cv2.LINE_AA)
                cv2.circle(img, pt, 7, red_color, 2, cv2.LINE_AA)

            # Clean tag
            mid_x = (p1[0] + p2[0]) // 2
            mid_y = (p1[1] + p2[1]) // 2
            tag_text = "STOP LINE"
            (tw, th), _ = cv2.getTextSize(tag_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            tx1 = mid_x - tw // 2 - 6
            ty1 = max(4, mid_y - th - 8)
            cv2.rectangle(img, (tx1, ty1), (tx1 + tw + 12, ty1 + th + 6), red_color, -1)
            cv2.putText(
                img,
                tag_text,
                (tx1 + 6, ty1 + th + 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (11, 15, 23),  # Dark text
                1,
                cv2.LINE_AA,
            )
        else:
            pts_arr = np.array(pts, dtype=np.int32)
            cv2.polylines(img, [pts_arr], False, red_color, 2, cv2.LINE_AA)

        return img

    def draw_traffic_light(self, img0, traffic_light_area, state):
        color_state = {
            "red": (68, 68, 239),     # #EF4444 BGR
            "yellow": (21, 204, 250), # #FACC15 BGR
            "green": (94, 197, 34),   # #22C55E BGR
        }
        if traffic_light_area is None or len(traffic_light_area) < 3:
            return img0

        height, width = img0.shape[:2]
        pts = [[int(x * width), int(y * height)] for x, y in traffic_light_area]
        pts_arr = np.array(pts, dtype=np.int32)
        img = img0.copy()

        c = color_state.get(str(state).lower(), (186, 160, 142))

        # Clean rounded box for signal
        x, y, w, h = cv2.boundingRect(pts_arr)
        r = 6
        cv2.rectangle(img, (x, y), (x + w, y + h), c, 2, cv2.LINE_AA)

        # Small crosshair marker at center
        cX = x + w // 2
        cY = y + h // 2
        arm = 5
        cv2.line(img, (cX - arm, cY), (cX + arm, cY), c, 1, cv2.LINE_AA)
        cv2.line(img, (cX, cY - arm), (cX, cY + arm), c, 1, cv2.LINE_AA)

        # Clean label tag with dark text
        tag_text = f"SIGNAL: {str(state).upper()}"
        (tw, th), _ = cv2.getTextSize(tag_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        ty1 = max(2, y - th - 6)
        cv2.rectangle(img, (x, ty1), (x + tw + 10, ty1 + th + 4), c, -1)
        cv2.putText(
            img,
            tag_text,
            (x + 5, ty1 + th + 1),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (11, 15, 23),
            1,
            cv2.LINE_AA,
        )

        return img
