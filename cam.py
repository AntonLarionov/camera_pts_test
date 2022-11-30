from onvif import ONVIFCamera
import numpy as np

class CamParam:
    def __init__ (self, min_pan, max_pan, min_tilt, max_tilt, min_zoom, max_zoom, matrix_size, aspect_ratio, zoom_type):
        self.pan = PanLimits(min_pan, max_pan)
        self.tilt = TiltLimits(min_tilt, max_tilt)
        self.zoom = ZoomLimits(min_zoom, max_zoom, zoom_type)
        self.martix = Matrix(matrix_size, aspect_ratio)
        self.abs = 0
        self.reinitconst()
        
    def reinitconst(self):
        mtrxmm = self.martix.size * 25.4 * 2 / 3 #Converting television! inches to mm
        arangle=np.arctan(self.martix.aspect)
        self.martix.sizeW = mtrxmm * np.sin(arangle)
        self.martix.sizeH = mtrxmm * np.cos(arangle)
        self.pan.scope = self.pan.max - self.pan.min
        self.pan.center = self.pan.max - self.pan.scope/2
        self.tilt.scope = self.tilt.max - self.tilt.min
        self.tilt.center = self.tilt.max - self.tilt.scope/2 
        self.zoom.zoom_rate = self.zoom.max/self.zoom.min
    
    def f2deg (self, focal: float):
        degW =np.degrees(2*np.arctan(self.martix.sizeW/(2*focal)))
        degH =np.degrees(2*np.arctan(self.martix.sizeH/(2*focal)))
        # print(degW, degH)
        return degW, degH

    # def pix2c (self, focal: float):
    #     degW =(np.degrees(2*np.arctan(self.martix.sizeW/(2*focal))))/self.martix.sizeW
    #     degH =(np.degrees(2*np.arctan(self.martix.sizeH/(2*focal))))/self.martix.sizeH
    #     return degW, degH
    
    def zoom2f (self, norm_zoom:float):
        if self.zoom.absolutezoom == 0:
            focal = norm_zoom *(self.zoom.max-self.zoom.min) + self.zoom.min
        else:
            focal = norm_zoom * self.zoom.max
        return focal
    def f2zoom (self, focal:float):
        if self.zoom.absolutezoom == 0:
            norm_zoom = (focal - self.zoom.min)/(self.zoom.max-self.zoom.min)
        else:
            norm_zoom = focal / self.zoom.max
        return norm_zoom
    def pan2deg (self, norm_pan: float):
        if (self.abs == True):
            deg_pan = norm_pan * 180
        else:
            deg_pan = (norm_pan * self.pan.scope / 2) + self.pan.center
        return deg_pan
    def deg2pan (self, deg_pan: float):
        if (self.abs == True):
            norm_pan = deg_pan / 180
        else:
            norm_pan = 2 * (deg_pan-self.pan.center) / self.pan.scope
        return norm_pan
    def tilt2deg (self, norm_tilt: float):
        if (self.abs == True):
            if (norm_tilt <= 0):
                deg_tilt = -norm_tilt * 180
            else:
                deg_tilt = 0
        else:
            deg_tilt = (-norm_tilt * self.tilt.scope / 2) + self.tilt.center
        return deg_tilt
    def deg2tilt (self, deg_tilt: float):
        if (self.abs == True):
            if (deg_tilt >= 0):
                norm_tilt = -deg_tilt / 180
            else:
                norm_tilt = 0
        else:
            norm_tilt = -2 * (deg_tilt - self.tilt.center) / self.tilt.scope
        return norm_tilt
    # def pix_to_angle(self, x_shift:float, y_shift:float):
    #     scale_x, scale_y = self.get_aov(self.f)
    #     print(self.anglew, self.angleh)
    #     pass
    
    def get_aov(self, focal):
        self.anglew=2*np.arctan(self.martix.sizeW/(2*focal))
        self.angleh=2*np.arctan(self.martix.sizeH/(2*focal))
        return (np.degrees(self.anglew), np.degrees(self.angleh))
     

class PanLimits:
    def __init__ (self, min_pan, max_pan):
        self.min = min_pan
        self.max = max_pan
        self.center = 0
        self.scope = 360
        
        
class TiltLimits:
    def __init__ (self, min_tilt, max_tilt):
        self.min = min_tilt
        self.max = max_tilt
        self.center = 0
        self.scope = 360
        
        
class ZoomLimits:
    def __init__ (self, min_zoom, max_zoom, zoom_type):
        self.min = min_zoom
        self.max = max_zoom
        self.aspect = 1
        self.absolutezoom = zoom_type
        zoom_rate = self.max/self.min
        
        
class Matrix:
    def __init__ (self, matrix_size, aspect_ratio):
        self.size = matrix_size
        self.aspect = aspect_ratio
        self.sizeW=1
        self.sizeH=1


class PTZ:
    def __init__ (self, ip, username, password, cam_conf, port=80, path='/etc/onvif/'):
        self.__ip = ip
        self.__port = port
        self.__user = username
        self.__pass = password
        self.__path = path
        self.cam_conf = cam_conf
        
    def connect(self):
        """
        Connecting to a network camera via onvif
        Returns:
            Return camera object, camera media object and camera ptz object
        """
        camera = ONVIFCamera(self.__ip, self.__port, self.__user, self.__pass, self.__path)
        media = camera.create_media_service()
        ptz = camera.create_ptz_service()
        mediatoken = camera.media.GetProfiles()[0].token
        ptztoken = camera.ptz.GetConfigurations()[0].token
        self.camera = camera
        self.media = media
        self.mediatoken = mediatoken
        self.ptz = ptz
        self.ptztoken=ptztoken
        return self.camera, self.media, self.ptz
    
    def getvideoconf(self, profile=0):
        mediaconf = mycam.media.GetProfiles()[profile]
        Encode = mediaconf.VideoEncoderConfiguration.Encoding
        W=mediaconf.VideoEncoderConfiguration.Resolution.Width
        H=mediaconf.VideoEncoderConfiguration.Resolution.Height
        fps=mediaconf.VideoEncoderConfiguration.RateControl.FrameRateLimit
        br=mediaconf.VideoEncoderConfiguration.RateControl.BitrateLimit
        return W, H, fps, br, Encode  
    
    def getptzstatus(self):  # нахрен не нужная функция, но пусть пока будет
        status = self.ptz.GetStatus(self.mediatoken)
        return status
  
    def getpos(self):
        """
        Query the absolute coordinates of the camera in the range of onvif values
        Returns:
            Returns the coordinates pan (-1,1), tilt (-1,1), zoom (0,1) #почему-то tilt -1,0.8
        """
        position = self.ptz.GetStatus(self.mediatoken).Position
        pan = position.PanTilt.x
        tilt = position.PanTilt.y
        zoom = position.Zoom.x
        return pan, tilt, zoom
    
    def pos_in_deg(self):
        pos = self.getpos()
        pan_deg = round(self.cam_conf.pan2deg(pos[0]),1)
        tilt_deg = round(self.cam_conf.tilt2deg(pos[1]),1)
        focal_mm = round(self.cam_conf.zoom2f(pos[2]),2)
        return (pan_deg, tilt_deg, focal_mm)

    
    def absmove(self, pan: float, tilt: float, zoom: float):
        """
        pan (-1,1), tilt (-1,1), zoom (0,1)
        """
        req = self.ptz.create_type('AbsoluteMove')
        req.ProfileToken = self.mediatoken
        req.Position = {'PanTilt': {'x': pan, 'y': tilt}, 'Zoom': zoom}
        req.Speed = {'PanTilt': {'x': 1, 'y': 1}, 'Zoom': 1}
        resp = self.ptz.AbsoluteMove(req)
        return resp
    
    def relmove(self, pan: float, tilt: float, zoom: float):
        """
        pan (-1,1), tilt (-1,1), zoom (0,1)
        """
        req = self.ptz.create_type('RelativeMove')
        req.ProfileToken = self.mediatoken
        req.Translation = {'PanTilt': {'x': pan, 'y': tilt}, 'Zoom': zoom}
        resp = self.ptz.RelativeMove(req)
        return resp
    
    def getpreset(self):  # нужно сделать пресеты
        req = self.ptz.create_type('GetPresets')
        req.ProfileToken = self.mediatoken
        resp = self.ptz.GetPresets(req)
        return resp
    
    def getlimits(self):  # пока заглушка под лимиты. Не понятно как делать)
        status = self.ptz.GetConfigurationOptions(self.ptztoken)
        return status
   
    def getrtsp(self):  # Ссылка на RTSP поток основного стрима
        req = self.media.create_type('GetStreamUri')
        req.StreamSetup = {'Stream': 'RTP-Unicast', 'Transport': {'Protocol': 'RTSP'}}
        req.ProfileToken = self.mediatoken
        resp = self.media.GetStreamUri(req)
        return resp.Uri
    
    def getsnap(self):#Снапшот
        resp = self.media.GetSnapshotUri(self.mediatoken)
        return resp.Uri
    
    def getptzconfs(self):
        resp = self.ptz.GetConfigurations()
        return resp
