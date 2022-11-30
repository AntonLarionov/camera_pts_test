from sys import flags
import cv2
import numpy as np
from skimage.filters import meijering
from scipy import fft,ifft
from skimage.transform import rescale, downscale_local_mean
import multiprocessing.dummy as mp
import os

#Функция формирует пару образов используя многопоточность
async def image_former(image, crop_factor: int = 1):
    #Преобразуем изображение в ЧБ
    image = cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)
    #Производим ресайз изображения в соответствии с кроп-фактором
    if crop_factor > 1:
        image = downscale_local_mean(image, (crop_factor,crop_factor))
    # Применяем фильтр и преобразование в частотную область
    # Если процессоров два или более - многопоточность.
    if os.cpu_count() < 2:
        default = meij(image,False)
        alternative = meij(image,True)
    else:
        with mp.Pool(2) as p:
            default, alternative = p.starmap(meij,[(image, False, crop_factor), (image, True, crop_factor)])
    return default, alternative

async def correlation(ref,img):
    return np.fft.ifftshift(np.fft.irfft2(ref*np.conjugate(img)))

async def unravel_index(conv):
    return np.unravel_index(conv.argmax(), conv.shape)
















#Подготовка образа изображения
def meij (image, alt, crop_factor:int = 1):
    #Применяем фильтры к изображению
    if not alt:
        result = meijering(image,sigmas=(1,3,5,9),mode='reflect')
    else:
        result = meijering(image,sigmas=(7,11,17,21),mode='reflect')
    return np.fft.rfft2(result)
