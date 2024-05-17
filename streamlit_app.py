import os
import streamlit as st
from streamlit_webrtc import webrtc_streamer, RTCConfiguration, VideoTransformerBase
import av
from openai import OpenAI
import cv2
import base64
from twilio.rest import Client
import asyncio
import logging

# Set up asyncio debugging
logging.basicConfig(level=logging.DEBUG)

# Ensure an event loop exists for the current thread
try:
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        raise RuntimeError("Event loop is closed")
except RuntimeError as e:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
loop.set_debug(True)

# Twilio setup
account_sid = st.secrets["account_sid"]
auth_token = st.secrets["auth_token"]
client = Client(account_sid, auth_token)
token = client.tokens.create()

# RTC Configuration
RTC_CONFIGURATION = RTCConfiguration(
    iceServers=[
        {"urls": ice_server["url"], "username": ice_server.get("username", ""),
         "credential": ice_server.get("credential", "")} for ice_server in token.ice_servers
    ]
)

print("\n" * 5)
print(token.ice_servers)
print("\n" * 5)

client = OpenAI(api_key=st.secrets["api_key"])

class VideoTransformer(VideoTransformerBase):
    frame = None

    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        self.frame = img
        print("Frame received and processed.")
        return av.VideoFrame.from_ndarray(img, format="bgr24")

def ask_question(image, question):
    _, img_encoded = cv2.imencode('.jpg', image)
    img_base64 = base64.b64encode(img_encoded).decode('utf-8')
    image_url = f"data:image/jpeg;base64,{img_base64}"

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Use the image to answer the provided question. Respond in Markdown."},
            {"role": "user", "content": [
                "This is a frame from a live video.",
                {"type": "image_url", "image_url": {"url": image_url, "detail": "low"}},
                question
            ]}
        ],
        temperature=0
    )
    print("OpenAI response received:", response)
    if response.choices:
        return response.choices[0].message.content
    else:
        return "No response received from the model."

def main():
    st.title("Live Video Q&A with AI")
    webrtc_ctx = webrtc_streamer(key="example", video_processor_factory=VideoTransformer, rtc_configuration=RTC_CONFIGURATION)
    question = st.text_input("Ask a question about what you see:")
    
    if st.button("Ask"):
        if webrtc_ctx.video_processor:
            frame = webrtc_ctx.video_processor.frame
            if frame is not None:
                print("Sending frame for question processing.")
                answer = ask_question(frame, question)
                st.write("Answer:", answer)
            else:
                st.write("No frames available yet.")
                print("No frame available to process.")
        else:
            st.write("Video stream not active. Please check your camera.")
            print("Video stream not active.")

if __name__ == "__main__":
    main()
