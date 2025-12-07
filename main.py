# Credits: Contains code from a tutorial https://www.youtube.com/watch?v=LWrRJx2wdWc

# == Depedencies ==
import os
import sys
import ffmpeg # pip install ffmpeg-python
from moviepy import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, ColorClip, ImageClip # pip install moviepy==2.0.0.dev2 && pip install imageio==2.25.1
from faster_whisper import WhisperModel # pip install faster-whisper
from PIL import Image, ImageDraw, ImageFont
import textwrap
import numpy as np
import json

# == Variables ==
max_chars = 45 # Original: 80
fontsize = 30 # Original: 80
padding = 20 # Original: 20

# == Helper functions ==
# The following functions are borrowed from a tutorial linked in "Credits"
def textToWords(segments):
	wordlevel_info = []
	for segment in segments:
		for word in segment.words:
			wordlevel_info.append({'word':word.word.strip(),'start':word.start,'end':word.end})
	return wordlevel_info

def textToLines(json_data, max_chars=max_chars, max_duration=3.0, max_gap=1.5):
	subtitles = []
	line = []
	line_duration = 0
	line_chars = 0
	for idx,word_data in enumerate(json_data):
		word = word_data["word"]
		start = word_data["start"]
		end = word_data["end"]
		line.append(word_data)
		line_duration += end - start
		temp = " ".join(item["word"] for item in line)
		# Check if adding a new word exceeds the maximum character count or duration
		new_line_chars = len(temp)
		duration_exceeded = line_duration > max_duration
		chars_exceeded = new_line_chars > max_chars
		if idx>0:
			gap = word_data['start'] - json_data[idx-1]['end']
			# print (word,start,end,gap)
			maxgap_exceeded = gap > max_gap
		else:
			maxgap_exceeded = False
		if duration_exceeded or chars_exceeded or maxgap_exceeded:
			if line:
				subtitle_line = {
					"word": " ".join(item["word"] for item in line),
					"start": line[0]["start"],
					"end": line[-1]["end"],
					"textcontents": line
				}
				subtitles.append(subtitle_line)
				line = []
				line_duration = 0
				line_chars = 0
	if line:
		subtitle_line = {
			"word" : " ".join(item["word"] for item in line),
			"start": line[0]["start"],
			"end": line[-1]["end"],
			"textcontents": line
		}
		subtitles.append(subtitle_line)
	return subtitles

def wrapText(text, font, max_width):
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        trial_line = f"{current_line} {word}".strip()
        width = font.getbbox(trial_line)[2]  # right coordinate
        if width <= max_width:
            current_line = trial_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines

def createCaption(textJSON, framesize, font_path="temp/arial.ttf", fontsize=fontsize, text_color="white", bg_color="black", padding=padding):
	text = textJSON["word"]
	start = textJSON["start"]
	end = textJSON["end"]
	duration = end - start
	# Fallback font if the specified TTF isn't found
	if not os.path.isfile(font_path):
		print("Failed to find font")
		return False
	# Load font and calculate padding
	font = ImageFont.truetype(font_path, fontsize)
	max_text_width = framesize[0] - 2 * padding
	lines = wrapText(text, font, max_text_width)
	line_height = font.getbbox("Ay")[3]
	img_height = len(lines) * (line_height + padding) + padding
	img_width = max_text_width + 2 * padding
	line_widths = [font.getbbox(line)[2] for line in lines]
	img_width = max(line_widths) + 2 * padding
	img_height = len(lines) * (line_height + padding) + padding
	img = Image.new("RGBA", (img_width, img_height), bg_color)
	draw = ImageDraw.Draw(img)
	y = padding
	# Create each line
	for line in lines:
		line_width = font.getbbox(line)[2]
		x = (img_width - line_width) // 2
		draw.text((x, y), line, font=font, fill=text_color)
		y += line_height + padding
	pos_x = (framesize[0] - img_width) // 2
	pos_y = framesize[1] - img_height - framesize[1] // 12
	np_img = np.array(img)
	clip = ImageClip(np_img).with_start(start).with_duration(duration).with_position((pos_x, pos_y))
	return [clip]

# == Main call ==
if __name__ == "__main__":

	# Checks correct usage
	if (len(sys.argv) != 3):
		print("Correct usage: python3 main.py [input_file_path] [output_directory]")
		quit()
	path = sys.argv[1]
	output_dir = sys.argv[2]
	output_path = output_dir + os.path.basename(path)
	output_file = output_dir + os.path.splitext(os.path.basename(path))[0] + ".txt"
	if (not os.path.exists(path)):
		print("Input path does not exist.")
		quit()
	if (os.path.exists(output_path) or os.path.exists(output_file)):
		print("Output file(s) already exists. Please delete or choose another path")
		quit()

	# Grab path and open video
	audio_path = "temp/temp.mp3"
	try:
		video = VideoFileClip(path)
		audio = video.audio
		print("Writing temporary audio clip at: " + audio_path)
		audio.write_audiofile(audio_path)
	except:
		print("Script failed to open file. Ensure correct usage.")
		quit()

	# Transcribe using Whisper
	model = WhisperModel("small")
	segments, info = model.transcribe(audio_path, word_timestamps=True) # Future direction: Has a prompt parameter for better transcriptions
	segments = list(segments)

	# Use algorithmic subtitle generation (borrowed from tutorial code)
	lines = textToLines(textToWords(segments))

	# Create an interface for editting these subtitles
	with open(output_file, 'w') as f:
		for line in lines:
			f.write(str(line["word"]) + '\n')
	print("Text file has been created")
	print("If necessary, make revisions to this file at: " + output_file)
	user_input = ""
	while (user_input != 'Y' and user_input != 'N'):
		user_input = input("Press 'Y/N' to merge onto video: ").upper()
	if (user_input == 'N'):
		print("Deleting temporary audio clip at: " + audio_path)
		os.remove(audio_path)
		quit()
	elif (user_input == 'Y'):
		with open(output_file, 'r') as f:
			for input_line, original_line in zip(f, lines):
				original_line["word"] = input_line

	# Burn subtitles into video (borrowed from tutorial code)
	frame_size = video.size
	line_clips = []
	for line in lines:
		out = createCaption(line, frame_size)
		line_clips.extend(out)
	for clip in line_clips:
		clip = clip.with_position(("center", frame_size[1] - clip.h - 80))

	# Output video and clean up
	final_video = CompositeVideoClip([video] + line_clips, size=frame_size)
	final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", preset="veryslow", threads=4) # Use ultrafast for debugging. For quality, use veryslow
	print("Deleting temporary audio clip at: " + audio_path)
	os.remove(audio_path)
	print("Success! File can be found at: " + output_path)
	quit()