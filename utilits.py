import json
import os
import requests
from requests.auth import HTTPBasicAuth
from requests.auth import HTTPDigestAuth
import logging
from skimage.io import imread

#Чтение конфигурационного файла камеры
def read_camera_config(path = "camera_config.json"):
    cfile = open(path)
    #Добавить ошибку если файл не существует
    config = json.load(cfile)
    cfile.close()
    return config

def check_folder(path):
    #Нужна еще проверка прав
    if os.path.exists(path):
        if os.path.isfile(path):
            os.remove(path)
            os.mkdir(path)
    else:
        os.mkdir(path)

async def camera_http_request(uri,user,password, auth_type = 'basic', timeout = 1):
    if auth_type == 'digest':
        auth = HTTPDigestAuth(user,password)
    else:
        auth = HTTPBasicAuth(user,password)

    try:
        response = requests.get(uri,auth=auth, stream = True, timeout=timeout)
        if response.status_code == 200:
            return response
        else:
            logging.warning("Error " + response.status_code + ": " + uri)
    except requests.ReadTimeout or requests.ConnectTimeout:
        logging.warning("Connection timeout: " + uri)
    except:
        logging.warning("Connection error to: " + uri)

async def get_snap(uri,user,password, auth_type = 'basic', timeout = 1):
    response = await camera_http_request(uri, user, password, auth_type, timeout)
    if response is not None:
        #Преобразую входную строку в изображение
        return imread(response.raw.read(), plugin='imageio')

async def api_get(uri,timeout = 100):
    try:
        response = requests.push(uri,timeout=timeout)
        if response.status_code == 200:
            return response
        else:
            logging.warning("Error " + response.status_code + ": " + uri)
    except requests.ReadTimeout or requests.ConnectTimeout:
        logging.warning("Connection timeout: " + uri)
    except:
        logging.warning("Connection error to: " + uri)

async def api_push(uri,timeout = 100):
    try:
        response = requests.get(uri,timeout=timeout)
        if response.status_code == 200:
            return response
        else:
            logging.warning("Error " + response.status_code + ": " + uri)
    except requests.ReadTimeout or requests.ConnectTimeout:
        logging.warning("Connection timeout: " + uri)
    except:
        logging.warning("Connection error to: " + uri)



    