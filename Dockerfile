FROM ubuntu:16.04

# install python
# RUN yum -y install gcc openssl-devel bzip2-devel libffi-devel zlib-devel
# RUN yum -y install wget make
RUN apt-get update
RUN apt-get install -y gcc libssl-dev  libffi-dev wget make
RUN wget https://www.python.org/ftp/python/3.9.7/Python-3.9.7.tgz && tar xzf Python-3.9.7.tgz 
RUN cd Python-3.9.7 && ./configure --enable-optimizations --enable-shared && make install
ENV LD_LIBRARY_PATH /Python-3.9.7

WORKDIR /app/
COPY ./requirements.txt .
RUN python3.9 -m pip install -r requirements.txt

COPY . .
RUN pyinstaller --add-data "src/opencl_sha256.cl:./" -F src/miner.py -n danila-miner