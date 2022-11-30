import os
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.responses import *
import presets
import utilits
import shift
from skimage import io #Наверное для теста
import numpy as np
import json
import cam
#Отключение мусора в логах
import logging
logger = logging.getLogger("uvicorn.error")
logger.propagate = False
import time
import random

#Загружаю конфигурационный файл камеры
config = utilits.read_camera_config()
#Инициирую PTZ (пока вот в таком хуевом виде, надо будет переделывать весь onvif)
###Костыли
absolute_zoom = False
if config.get('configuration').get('focal').get('scale') == 'absolute':
    absolute_zoom = True
aspect = float(config.get('configuration').get('matrix').get('width')) / float(config.get('configuration').get('matrix').get('heigth'))


param = cam.CamParam(min_pan=float(config.get('configuration').get('position').get('pan_min')),
    max_pan=float(config.get('configuration').get('position').get('pan_max')),
    min_tilt=float(config.get('configuration').get('position').get('tilt_min')),
    max_tilt=float(config.get('configuration').get('position').get('tilt_max')),
    min_zoom=float(config.get('configuration').get('focal').get('min')),
    max_zoom=float(config.get('configuration').get('focal').get('max')),
    matrix_size=float(config.get('configuration').get('matrix').get('size')),
    aspect_ratio=aspect,
    zoom_type=absolute_zoom    
    )

camera = cam.PTZ(ip = config.get('network').get('ip'),
    port = int(config.get('network').get('port')),
    username= config.get('auth').get('login'),
    password=config.get('auth').get('password'),
    cam_conf=param, path='/etc/onvif/')
camera.connect()
uri = camera.getsnap()
###//Костыли




#После инициации сразу получаю ссылку на снапы и сохраняю в переменной
#Добавляю пути к папкам с пресетами и референсами и создаю папки
preset_path = "Presets"
reference_path = "References"
utilits.check_folder(preset_path)
utilits.check_folder(reference_path)
utilits.check_folder("Snaps")



#Создаю объект fastapi
# app = FastAPI(debug=True)
app = FastAPI(debug=False)

async def check_content_type(content_type):
    '''Check if file content-type is an image.
       Returns acceptable file extension.'''

    image_formats = ("image/png", "image/jpeg", "image/jpg")
    if content_type not in image_formats:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                            detail="Not acceptable image format!")

    file_ext = content_type.split('/')[-1]
    return file_ext


#Запрос текущих координат
@app.get("/api/getpos")
async def getpos():
    t0 = time.clock_gettime(time.CLOCK_MONOTONIC)
    x,y,z =camera.getpos()
    return {"rel":{"x":x, "y":y, "z":z}, "abs": {"x":param.pan2deg(x), "y":param.tilt2deg(y), "z":param.zoom2f(z)}, "time":time.clock_gettime(time.CLOCK_MONOTONIC) - t0}


#Работа с пресетами
##Добавление
@app.post("/api/preset/add",status_code=200)
async def api_preset_add(id:str, response: Response, crop_factor: int = 4):
    '''Create new preset with current PTZ position and reference image'''
    if not os.path.exists(preset_path + "/" + id + ".json"):
        #Получаем координаты с камеры
        x,y,z =camera.getpos()#Надо обработку ошибки, но это надо переписывать PTZ
        ##Загрузка снапа с камеры
        reference = await utilits.get_snap(uri,str(config.get('auth').get('login')),str(config.get('auth').get('password')),
            str(config.get('auth').get('type')),float(config.get('configuration').get('timeout').get('response')))#Добавить URL
        if reference is not None:
            #Получаю образа изображения, далее сохраняю все это под именем <id>.jpg и <id>.npy
            images = await shift.image_former(reference,crop_factor=crop_factor)
            ref_fpath = reference_path + "/" + id + ".jpg"
            io.imsave(ref_fpath, reference, quality = 100)
            img_fpath = reference_path + "/" + id + ".npy"
            np.save(img_fpath,images)
            #Подготавливаю json
            position = {"x": str(x), "y": str(y), "z": str(z)}
            preset = {"id": id, "position": position, "ref":ref_fpath, "image": img_fpath, "crop": str(crop_factor)}
            preset_fpath = preset_path + "/" + id + ".json"
            await presets.write_preset_config(preset_fpath, preset)
            return {"id": id, "position":position, "crop": str(crop_factor)}
        else:
            response.status_code=status.HTTP_400_BAD_REQUEST #Надо бы потом добавить конкретику по ошибкам
            return "Image download error"
    else:
        response.status_code=status.HTTP_400_BAD_REQUEST #Надо бы потом добавить конкретику по ошибкам
        return "Id " + id + " is exist!"

        
##Обновление
@app.post("/api/preset/update",status_code=200)
async def api_preset_upd(id:str,response: Response):
    '''Update old preset on current PTZ position and reference image'''
    if os.path.exists(preset_path + "/" + id + ".json"):
        #Получаем координаты с камеры
        x,y,z =camera.getpos()#Надо обработку ошибки, но это надо переписывать PTZ
        ##Загрузка снапа с камеры
        reference = await utilits.get_snap(uri,str(config.get('auth').get('login')),str(config.get('auth').get('password')),
            str(config.get('auth').get('type')),float(config.get('configuration').get('timeout').get('response')))#Добавить URL
        if reference is not None:
            preset_fpath = preset_path + "/" + id + ".json"
            preset = await presets.read_preset_config(preset_fpath)
            #Получаю образа изображения, далее сохраняю все это под именем <id>.jpg и <id>.npy
            images = await shift.image_former(reference,crop_factor=int(preset.get('crop')))
            ref_fpath = reference_path + "/" + id + ".jpg"
            io.imsave(ref_fpath, reference, quality = 100)
            img_fpath = reference_path + "/" + id + ".npy"
            np.save(img_fpath,images)
            #Подготавливаю json
            position = {"x": str(x), "y": str(y), "z": str(z)}
            preset.update({"position":position,"ref":ref_fpath,"image": img_fpath})  
            await presets.write_preset_config(preset_fpath, preset)
            return {"id": id, "position":position, "crop": str(preset.get('crop'))}
        else:
            response.status_code=status.HTTP_400_BAD_REQUEST #Надо бы потом добавить конкретику по ошибкам
            return "Image download error"
    else:
        response.status_code=status.HTTP_400_BAD_REQUEST #Надо бы потом добавить конкретику по ошибкам
        return "Id " + id + " is not exist!"
##Обновление положения без обновления референса
@app.post("/api/preset/update_coordinats",status_code=200)
async def api_preset_upd(id:str,response: Response):
    '''Update old preset on current PTZ position WITHOUT update reference image'''
    preset_fpath = preset_path + "/" + id + ".json"
    preset = await presets.read_preset_config(preset_fpath)
    x,y,z =camera.getpos()
    position = {"x": str(x), "y": str(y), "z": str(z)}
    preset.update({"position":position})
    await presets.write_preset_config(preset_fpath, preset)
    return {"id": id, "position":position, "crop": preset.get("crop")}
##Удаление
@app.post("/api/preset/delete",status_code=200)
async def api_preset_del(id:str,response: Response):
    '''Delete current preset'''
    if os.path.exists(preset_path + "/" + id + ".json"):
        preset = await presets.read_preset_config(preset_path + "/" + id + ".json")
        if os.path.exists(preset.get('ref')):
            os.remove(preset.get('ref'))
        if os.path.exists(preset.get('image')):
            os.remove(preset.get('image'))
        os.remove(preset_path + "/" + id + ".json")
        return "Preset " + id + " removed."
    else:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return "Preset " + id + " not exist."

##Загрузка нового референса
@app.post("/api/preser/ref_upload",status_code=200)
async def api_preset_refupd(id:str,response: Response, loaded_image: UploadFile=File()):
    '''Load new reference image from file'''
    if loaded_image.content_type == "image/jpeg":
        reference = io.imread(loaded_image.file, plugin='imageio')
        if reference.shape[1] == int(config.get('configuration').get('matrix').get('width')) and reference.shape[0] == int(config.get('configuration').get('matrix').get('heigth')):
            if os.path.exists(preset_path + "/" + id + ".json"):
                preset = await presets.read_preset_config(preset_path + "/" + id + ".json")
                images = await shift.image_former(reference,crop_factor=int(preset.get('crop')))
                io.imsave(preset.get('ref'), reference, quality = 100)
                np.save(preset.get('image'),images)
                return "Refetence upload"
            else:
                response.status_code=status.HTTP_400_BAD_REQUEST
                return "Id " + id + " not exist" 
        else:
            response.status_code=status.HTTP_400_BAD_REQUEST
            return "Image size must be some as camera resolution"
            # return {"image": {"x":reference.shape[1], "y": reference.shape[0]},"date": {"x":config.get('configuration').get('matrix').get('width'), "y": config.get('configuration').get('matrix').get('heigth')}}

    else:
        response.status_code=status.HTTP_400_BAD_REQUEST
        return "Only JPG image must be load"
##Выгрузка с сервера референса
@app.get("/api/preser/ref_download",status_code=200)
async def api_preset_refd(id:str,response: Response):
    '''Get reference image from api'''
    if os.path.exists(preset_path + "/" + id + ".json"):
        preset = await presets.read_preset_config(preset_path + "/" + id + ".json")
        image_path = preset.get('ref')
        return FileResponse(path=image_path,media_type="image/jpeg",filename="preset"+ id + ".jpg")
    else:
        response.status_code=status.HTTP_400_BAD_REQUEST
        return "id not exist"
##Список существубщих пресетов и их координат
@app.get("/api/preset/list")
async def api_preset_list():
    '''Get preset list'''
    listing = dict()
    with os.scandir(preset_path) as filename:
        for entry in filename:
            if entry.is_file():
                ppath = preset_path + "/"+entry.name
                pjson = await presets.read_preset_config(ppath)
                listing.update({pjson.get('id'):pjson.get('position')})
    return listing
@app.get("/apt/image")
async def return_image():
    reference = await utilits.get_snap(uri,str(config.get('auth').get('login')),str(config.get('auth').get('password')),
            str(config.get('auth').get('type')),float(config.get('configuration').get('timeout').get('response')))#Добавить URL\
    name = "Snaps/" + str(int(time.clock_gettime(time.CLOCK_MONOTONIC))) + ".jpg"
    io.imsave(name,reference)

    return FileResponse(path=name,media_type="image/jpeg",filename="snap.jpg")
    



@app.post("/api/ptz/goto",status_code = 200)
async def goto_ptz (x:float, y:float, z:float):
    t0 = time.clock_gettime(time.CLOCK_MONOTONIC)
    camera.absmove(x,y,z)
    status = camera.getptzstatus()
    ptz_status = status.MoveStatus.PanTilt
    zoom_status = status.MoveStatus.Zoom
    while ptz_status!='IDLE' or zoom_status!='IDLE':
        status = camera.getptzstatus()
        ptz_status = status.MoveStatus.PanTilt
        zoom_status = status.MoveStatus.Zoom
    t1 = time.clock_gettime(time.CLOCK_MONOTONIC)
    return t1-t0
@app.post("/api/ptz/gotoabs",status_code = 200)
async def goto_ptz_abs (x:float, y:float, z:float):
    t0 = time.clock_gettime(time.CLOCK_MONOTONIC)
    camera.absmove(param.deg2pan(x),param.deg2tilt(y),param.f2zoom(z))
    status = camera.getptzstatus()
    ptz_status = status.MoveStatus.PanTilt
    zoom_status = status.MoveStatus.Zoom
    while ptz_status!='IDLE' or zoom_status!='IDLE':
        status = camera.getptzstatus()
        ptz_status = status.MoveStatus.PanTilt
        zoom_status = status.MoveStatus.Zoom
    t1 = time.clock_gettime(time.CLOCK_MONOTONIC)
    return t1-t0
@app.post("/api/ptz/goto_preset",status_code = 200)
async def goto_preset (id:str,response: Response):
    t0 = time.clock_gettime(time.CLOCK_MONOTONIC)
    if os.path.exists(preset_path + "/" + id + ".json"):
        preset = await presets.read_preset_config(preset_path + "/" + id + ".json")
        x = float(preset.get("position").get('x'))
        y = float(preset.get("position").get('y'))
        z = float(preset.get("position").get('z'))
        camera.absmove(x,y,z)
        status = camera.getptzstatus()
        ptz_status = status.MoveStatus.PanTilt
        zoom_status = status.MoveStatus.Zoom
        while ptz_status!='IDLE' or zoom_status!='IDLE':
            status = camera.getptzstatus()
            ptz_status = status.MoveStatus.PanTilt
            zoom_status = status.MoveStatus.Zoom
        t1 = time.clock_gettime(time.CLOCK_MONOTONIC)
        return t1-t0
    else:
        response.status_code=status.HTTP_400_BAD_REQUEST #Надо бы потом добавить конкретику по ошибкам
        return "Id not exist"

# @app.get("/api/shift/calculate",status_code = 200)
@app.get("/api/shift/calculate")
# async def pixel_shift(id:str,response: Response):
async def pixel_shift(id:str):
    if os.path.exists(preset_path + "/" + id + ".json"):
        t0 = time.clock_gettime(time.CLOCK_MONOTONIC)
        snap = await utilits.get_snap(uri,str(config.get('auth').get('login')),str(config.get('auth').get('password')),
            str(config.get('auth').get('type')),float(config.get('configuration').get('timeout').get('response')))
        px,py,pz =camera.getpos()
        if snap is not None:
            preset = await presets.read_preset_config(preset_path + "/" + id + ".json")
            crop_factor = float(preset.get('crop'))
            t1 = time.clock_gettime(time.CLOCK_MONOTONIC)
            img1, img2 = await shift.image_former(snap,crop_factor=int(preset.get('crop')))
            t2 = time.clock_gettime(time.CLOCK_MONOTONIC)
            ref1, ref2 = np.load(preset.get('image'))
            t3 = time.clock_gettime(time.CLOCK_MONOTONIC)

            cor1 = await shift.correlation(ref1,img1)
            cor2 = await shift.correlation(ref2,img2)

            dy1, dx1 = await shift.unravel_index(cor1)
            dy2, dx2 = await shift.unravel_index(cor2)
            x1 = (cor1.shape[1] / 2 - dx1) * crop_factor
            y1 = (cor1.shape[0] / 2 - dy1) * crop_factor
            x2 = (cor2.shape[1] / 2 - dx2) * crop_factor
            y2 = (cor2.shape[0] / 2 - dy2) * crop_factor
            # max_err = np.sqrt(np.square(cor1.shape[0]* crop_factor)+np.square(cor1.shape[1]* crop_factor))
            x_err = abs(x1-x2)
            y_err = abs(y1-y2)
            err = np.sqrt(np.square(x_err)+np.square(y_err))
            # correlation = cor1[x1][y1]/cor2[x1][y1]
            t4 = time.clock_gettime(time.CLOCK_MONOTONIC)
            error = False
            #Не более трети кадра
            if abs(x1) > cor1.shape[1]*0.4*crop_factor:
                error = True
                # print("x")
            if abs(y1) > cor1.shape[0]*0.4*crop_factor:
                error = True
                # print("y")
            if err>30:
                error = True
                # print("e")\
            
            if error:
                x_correc = float(preset.get("position").get("x"))
                y_correc = float(preset.get("position").get("y"))
                z_correc = float(preset.get("position").get("z"))
            else:
                cx, cy = param.f2deg(param.zoom2f(pz))
                cx = cx/float(config.get("configuration").get("matrix").get("width"))
                cy = cy/float(config.get("configuration").get("matrix").get("heigth"))
                x_correc = param.deg2pan(param.pan2deg(px) + x1*cx)
                y_correc = param.deg2tilt(param.tilt2deg(py) + y1*cy)
                z_correc = pz
                #Работает некорректно!
                # print(param.pan2deg(x_correc),param.tilt2deg(y_correc))
                

            return {"result":{"x":x1, "y":y1, "e":error, "kerr":err},"correction":{"x":x_correc, "y":y_correc,"z":z_correc},"time":{"img_load":t1-t0, "img_proc":t2-t1, "ref_load":t3-t2, "calculation":t4-t3}}

    #     else:
    #         response.status_code=status.HTTP_400_BAD_REQUEST #Надо бы потом добавить конкретику по ошибкам
    #         return "Image download error"
    # else:
    #     response.status_code=status.HTTP_400_BAD_REQUEST #Надо бы потом добавить конкретику по ошибкам
    #     return "Id not exist"

@app.post("/test/estimation")
async def t_estimation(x:float, y:float, z:float, id:str):
    if os.path.exists(preset_path + "/" + id + ".json"):
        preset = await presets.read_preset_config(preset_path + "/" + id + ".json")
        #Перемещаем в позицию x,y,z
        t0 = time.clock_gettime(time.CLOCK_MONOTONIC)
        camera.absmove(x,y,z)
        status = camera.getptzstatus()
        ptz_status = status.MoveStatus.PanTilt
        zoom_status = status.MoveStatus.Zoom
        while ptz_status!='IDLE' or zoom_status!='IDLE':
            status = camera.getptzstatus()
            ptz_status = status.MoveStatus.PanTilt
            zoom_status = status.MoveStatus.Zoom
        resopition_time = time.clock_gettime(time.CLOCK_MONOTONIC) - t0
        #Получаем снап после репозиционирования
        # stat = Response
        shift = await pixel_shift(id)
        shift["time"]["PTZ"] = resopition_time
        # x_esterr = abs(shift.get("correction").get("x") - float(preset.get("position").get("x")))
        # y_esterr = abs(shift.get("correction").get("y") - float(preset.get("position").get("y")))
        # print(param.tilt2deg(y_esterr))
        # cx, cy = param.f2deg(param.zoom2f(float(preset.get("position").get("z"))))
        # cx = cx/float(config.get("configuration").get("matrix").get("width"))
        # cy = cy/float(config.get("configuration").get("matrix").get("heigth"))
        # x_esterr = x_esterr * param.pan.scope/2
        # y_esterr = y_esterr * param.tilt.scope/2

        # print(param.tilt2deg(cy))

                # x_correc = param.deg2pan(param.pan2deg(px) + x1*cx)
                # y_correc = param.deg2tilt(param.tilt2deg(py) + y1*cy)
                # z_correc = pz
        # shift["pixerr_estimate"] = {"x":round(x_esterr/cx,0), "y":round(y_esterr/cy)}
        return shift
@app.post("/test/one_test")
async def t_one(id:str, max_shift_x:int=480, max_shift_y:int = 270):
    if os.path.exists(preset_path + "/" + id + ".json"):
        preset = await presets.read_preset_config(preset_path + "/" + id + ".json")
        x = float(preset.get("position").get("x"))
        y = float(preset.get("position").get("y"))
        z = float(preset.get("position").get("z"))

        cx, cy = param.f2deg(param.zoom2f(z))
        cx = cx/float(config.get("configuration").get("matrix").get("width"))
        cy = cy/float(config.get("configuration").get("matrix").get("heigth"))

        sh_x = random.uniform(-1* max_shift_x,max_shift_x)
        sh_y = random.uniform(-1* max_shift_y,max_shift_y)
        x_shifted = param.deg2pan(param.pan2deg(x) + sh_x*cx)
        y_shifted = param.deg2tilt(param.tilt2deg(y) + sh_y*cy)
        goto = await t_estimation(x_shifted, y_shifted, z, id)

        x_corrected = goto["correction"]["x"]
        y_corrected = goto["correction"]["y"]

        correct = await t_estimation(x_corrected, y_corrected, z, id)

        camera.absmove(float(preset["position"]["x"]),float(preset["position"]["y"]),float(preset["position"]["z"]))

        return {"pre_correction":goto, "post_correction":correct, "preset_pos": preset.get("position"), "goto_pos":{"x":x_shifted,"y":y_shifted, "xpix":sh_x, "ypix":sh_y }}

