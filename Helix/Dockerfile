# Dockerfile 
FROM python:3.10 
 
# Install system dependencies for Tkinter 
RUN apt-get update && apt-get install -y \ 
    python3-tk \ 
    x11-apps \ 
    xauth \ 
    x11-xserver-utils \ 
    && rm -rf /var/lib/apt/lists/* 
 
# Set working directory 
WORKDIR /app 
 
# Copy requirements first for better caching 
COPY requirements.txt . 
RUN pip install --no-cache-dir -r requirements.txt 

RUN pip install requests
# Copy application files 
COPY . . 
 
# Set environment variables for X11 forwarding 
ENV DISPLAY=host.docker.internal:0.0 
ENV QT_X11_NO_MITSHM=1 
 
# Run the application 
CMD ["python", "helix.py"]