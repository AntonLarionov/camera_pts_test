import json
#Чтение пресета из файла
async def read_preset_config(path):
    pfile = open(path)
    #Добавить ошибку если файл не существует
    preset = json.load(pfile)
    pfile.close()
    return preset

#Запись пресета в файл
async def write_preset_config(path, preset_dict):
    pfile = open(path,'w')
    preset=json.dumps(preset_dict,indent=4)
    pfile.write(preset)
    pfile.close
    #Добавить ошибку если файл не существует
