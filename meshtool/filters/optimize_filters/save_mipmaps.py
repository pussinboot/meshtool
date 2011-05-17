from meshtool.args import *
from meshtool.filters.base_filters import *
import os.path
import posixpath

import collada
import Image
from StringIO import StringIO
import math
import tarfile
import ImageFile

def getMipMaps(mesh):
    #Following is a workaround for setting quality=95, optimize=1 when encoding JPEG
    #Otherwise, an error is output when trying to save
    #Taken from http://mail.python.org/pipermail/image-sig/1999-August/000816.html
    ImageFile.MAXBLOCK = 20*1024*1024 # default is 64k, setting to 20MB to handle large textures
    
    mipmaps = {}
    for effect in mesh.effects:
        for prop in effect.supported:
            propval = getattr(effect, prop)
            if isinstance(propval, collada.material.Map):
                image_name = propval.sampler.surface.image.path
                image_data = propval.sampler.surface.image.data

                try:
                    im = Image.open(StringIO(image_data))
                    im.load()
                except IOError:
                    from panda3d.core import Texture
                    from panda3d.core import StringStream
                    from panda3d.core import PNMImage
                    
                    #PIL failed, so lets try DDS reader with panda3d
                    t = Texture(image_name)
                    success = t.readDds(StringStream(image_data))
                    if success == 0:
                        raise FilterException("Failed to read image file %s" % image_name)
        
                    #convert DDS to PNG
                    outdata = t.getRamImageAs('RGBA').getData()
                    try:
                        im = Image.fromstring('RGBA', (t.getXSize(), t.getYSize()), outdata)
                        im.load()
                    except IOError:
                        raise FilterException("Failed to read image file %s" % image_name)
                    
                #Keep JPG in same format since JPG->PNG is pretty bad
                if im.format == 'JPEG':
                    output_format = 'JPEG'
                    output_extension = 'jpg'
                    output_options = {'quality': 95, 'optimize':True}
                else:
                    output_format = 'PNG'
                    output_extension = 'png'
                    output_options = {'optimize':True}
                    
                #store a copy to the original image so we can resize from it directly each time
                orig_im = im
                
                width, height = im.size
                
                #round down to power of 2
                width = int(math.pow(2, int(math.log(width, 2))))
                height = int(math.pow(2, int(math.log(height, 2))))

                pil_images = []

                while True:
                    im = orig_im.resize((width, height), Image.ANTIALIAS)
                    pil_images.insert(0, im)
                    if width == 1 and height == 1:
                        break
                    width = max(width / 2, 1)
                    height = max(height / 2, 1)

                tar_buf = StringIO()
                tar = tarfile.TarFile(fileobj=tar_buf, mode='w')
              
                cur_offset = 0
                byte_ranges = []
                for i, pil_img in enumerate(pil_images):
                    buf = StringIO()
                    pil_img.save(buf, output_format, **output_options)
                    file_len = buf.tell()
                    cur_name = '%dx%d.%s' % (pil_img.size[0], pil_img.size[1], output_extension)
                    tar_info = tarfile.TarInfo(name=cur_name)
                    tar_info.size=file_len
                    buf.seek(0)
                    tar.addfile(tarinfo=tar_info, fileobj=buf)
                    
                    #tar files have a 512 byte header
                    cur_offset += 512
                    file_start = cur_offset
                    
                    byte_ranges.append((file_start, file_len))
                    
                    #file lengths are rounded up to nearest 512 multiple
                    file_len = 512 * (int(file_len / 512.0) + 1)
                    cur_offset += file_len
                
                tar.close()
                
                mipmaps[propval.sampler.surface.image.path] = (tar_buf.getvalue(), byte_ranges)
    return mipmaps

def saveMipMaps(mesh):
    mipmaps = getMipMaps(mesh)
    
    if not mesh.filename:
        return False
    reldir = os.path.dirname(mesh.filename)
    if not os.path.isdir(reldir):
        return False
    
    for imgpath, (tarbuf, ranges) in mipmaps.iteritems():
        saveto = os.path.normpath(os.path.join(reldir, imgpath))
        saveto += '.tar'
        f = open(saveto, 'wb')
        f.write(tarbuf)
        f.close()
    return True

def FilterGenerator():
    class SaveMipMapsFilter(OpFilter):
        def __init__(self):
            super(SaveMipMapsFilter, self).__init__('save_mipmaps', 'Saves mipmaps to disk in tar format in the same location as textures but with an added .tar. The archive will contain PNG or JPG images.')
        def apply(self, mesh):
            succ = saveMipMaps(mesh)
            if not succ:
                raise FilterException('Failed to save mipmaps')
            return mesh
        
    return SaveMipMapsFilter()