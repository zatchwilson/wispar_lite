# Use the official Python runtime image
FROM python:3.12 AS builder
 
# Create the app directory
RUN mkdir /app
 
# Set the working directory inside the container
WORKDIR /app
 
# Prevents Python from writing pyc files to disk
ENV PYTHONDONTWRITEBYTECODE=1
#Prevents Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1 
 
# Upgrade pip
RUN pip install --upgrade pip 
 
# Copy the Django project  and install dependencies
COPY requirements.txt  /app/
 
# run this command to install all dependencies 
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12

RUN apt-get -y update
RUN apt-get -y upgrade
RUN apt-get install -y ffmpeg calibre

RUN useradd -m -r appuser && \
    mkdir /app&& \
    mkdir /app/volume&& \
    mkdir /app/volume/staticfiles&& \
    mkdir /app/volume/books&& \
    mkdir /app/volume/books/temp&& \
    chown -R appuser /app


# Copy the Python dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/



# Set the working directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser . .

# Set environment variables to optimize Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1 

# Switch to non-root user
USER appuser
 
# Expose the Django port
EXPOSE 8000

RUN mkdir -p /app/nltk_data && \
   python -c "import nltk; nltk.download('stopwords', download_dir='/app/nltk_data')"