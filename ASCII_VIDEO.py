import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os
from tqdm import tqdm
import time
import multiprocessing as mp

# 画像を作成するために使用されるASCII文字
ASCII_CHARS_BW = "@%#*+=-:. "
ASCII_CHARS_COLOR = "@%#S&8BWM#oahkbdpqwmZO0QLCJUYXzcvunxrjft/|()1{}[]?-_+~<>i!lI;:,\"^`'. "

# 各ピクセルをASCII文字に変換
def pixel_to_ascii(pixel_value, ascii_chars):
    return ascii_chars[int(pixel_value / 256 * len(ascii_chars))]

# 画像をASCIIに変換
def image_to_ascii(image, num_cols, char_width, char_height, full_color):
    if full_color:
        resized_image = cv2.resize(image, (num_cols, int(num_cols * image.shape[0] / image.shape[1] * char_height / char_width)))
        ascii_image = []
        for row in resized_image:
            ascii_row = "".join([pixel_to_ascii(pixel[0], ASCII_CHARS_COLOR) for pixel in row])  # Using the first channel for ASCII conversion
            ascii_image.append(ascii_row)
        return ascii_image, resized_image
    else:
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        height, width = gray_image.shape
        aspect_ratio = height / float(width)
        num_rows = int(num_cols * aspect_ratio * (char_height / char_width))
        resized_gray_image = cv2.resize(gray_image, (num_cols, num_rows))
        ascii_image = []
        for row in resized_gray_image:
            ascii_row = "".join([pixel_to_ascii(pixel, ASCII_CHARS_BW) for pixel in row])
            ascii_image.append(ascii_row)
        return ascii_image, None

# ビデオライターオブジェクトを作成
def create_video_writer(output_path, frame_size, fps):
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    return cv2.VideoWriter(output_path, fourcc, fps, frame_size)

def process_frame(frame, num_cols, width, height, font_path, font_size, full_color, bg_color=None, txt_color=None):
    font = ImageFont.truetype(font_path, font_size)
    char_width, char_height = font.getbbox('A')[2:4]
    ascii_frame, resized_image = image_to_ascii(frame, num_cols, char_width, char_height, full_color)

    if full_color:
        if bg_color is not None:
            img_pil = Image.new('RGB', (num_cols * char_width, len(ascii_frame) * char_height), color=(bg_color, bg_color, bg_color))
        else:
            img_pil = Image.new('RGB', (num_cols * char_width, len(ascii_frame) * char_height))
        draw = ImageDraw.Draw(img_pil)
        y_text = 0
        for i, line in enumerate(ascii_frame):
            x_text = 0
            for j, char in enumerate(line):
                color = tuple(resized_image[i, j][:3])  # Take RGB values from the resized image
                draw.text((x_text, y_text), char, font=font, fill=color)
                x_text += char_width
            y_text += char_height
    else:
        img_pil = Image.new('L', (num_cols * char_width, len(ascii_frame) * char_height), color=bg_color)
        draw = ImageDraw.Draw(img_pil)
        y_text = 0
        for line in ascii_frame:
            draw.text((0, y_text), line, font=font, fill=txt_color)
            y_text += char_height

    img_np = np.array(img_pil)
    if full_color:
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    else:
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_GRAY2BGR)
    
    img_bgr = cv2.resize(img_bgr, (width, height))
    return img_bgr

def main():
    # フェーズ1: Processing - ビデオファイルを読み込み
    video_path = '/video/path/is/here'
    cap = cv2.VideoCapture(video_path)

    # ビデオが正常に開かれたか確認
    if not cap.isOpened():
        print("エラー: ビデオを開くことができませんでした。")
        exit()

    # ビデオのプロパティを取得
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # ユーザーに背景色とテキスト色を入力してもらう
    background_color = input("背景色を入力してください (b/w/c): ").strip().lower()
    if background_color == "b" or background_color == "ｂ":
        text_color = "white"
        bg_color = 0
        txt_color = 255
        suffix = "（ASCII・Black）"
        full_color = False
    elif background_color == "w" or background_color == "ｗ":
        text_color = "black"
        bg_color = 255
        txt_color = 0
        suffix = "（ASCII・White）"
        full_color = False
    elif background_color == "c" or background_color == "ｃ":
        color_mode = input("カラーの背景色を選択してください (b/w): ").strip().lower()
        if color_mode == "b" or color_mode == "ｂ":
            text_color = "white"
            bg_color = 0
            txt_color = None
            suffix = "（ASCII・FullColor・Black）"
            full_color = True
        elif color_mode == "w" or color_mode == "ｗ":
            text_color = "black"
            bg_color = 255
            txt_color = None
            suffix = "（ASCII・FullColor・White）"
            full_color = True
        else:
            print("無効な入力です。b, wのいずれかを入力してください。")
            exit()
    else:
        print("無効な入力です。b, w, cのいずれかを入力してください。")
        exit()

    # ビデオライターを作成
    output_path = video_path.rsplit('.', 1)[0] + suffix + '.mp4'
    out = create_video_writer(output_path, (width, height), fps)

    # フォント設定
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
    font_size = 10
    font = ImageFont.truetype(font_path, font_size)
    char_width, char_height = font.getbbox('A')[2:4]
    num_cols = width // char_width  # スペースを考慮して列数を調整

    # 使用するワーカー数を設定 (総CPU数 - 2)
    num_workers = mp.cpu_count() - 2
    pool = mp.Pool(num_workers)

    # フェーズ2: Collecting - プログレスバー付きでフレームを読み取り処理
    start_time = time.time()
    results = []

    with tqdm(total=total_frames, desc="Processing", unit="frame") as pbar:
        for _ in range(total_frames):
            ret, frame = cap.read()
            if not ret:
                break
            if full_color:
                result = pool.apply_async(process_frame, args=(frame, num_cols, width, height, font_path, font_size, full_color, bg_color, txt_color))
            else:
                result = pool.apply_async(process_frame, args=(frame, num_cols, width, height, font_path, font_size, full_color, bg_color, txt_color))
            results.append(result)
            pbar.update(1)

    # フェーズ3: Writing - 処理済みフレームをビデオに書き込み
    for result in tqdm(results, desc="Writing", unit="frame"):
        out.write(result.get())

    # ビデオキャプチャとライターオブジェクトを解放
    cap.release()
    out.release()
    pool.close()
    pool.join()

if __name__ == "__main__":
    main()
