import numpy
import collada
import posixpath
import struct
from math import pi, sin, cos
import Image
from StringIO import StringIO

from direct.task import Task
from direct.showbase.ShowBase import ShowBase
from panda3d.core import GeomVertexFormat, GeomVertexArrayData
from panda3d.core import GeomVertexData, GeomEnums, GeomVertexWriter
from panda3d.core import GeomLines, GeomTriangles, Geom, GeomNode, NodePath
from panda3d.core import PNMImage, Texture, StringStream
from panda3d.core import RenderState, TextureAttrib, MaterialAttrib, Material
from panda3d.core import VBase4, Vec4, Mat4, SparseArray
from panda3d.core import AmbientLight, DirectionalLight
from panda3d.core import Character, PartGroup, CharacterJoint
from panda3d.core import TransformBlend, TransformBlendTable, JointVertexTransform
from panda3d.core import GeomVertexAnimationSpec, GeomVertexArrayFormat, InternalName
from panda3d.core import AnimBundle, AnimGroup, AnimChannelMatrixXfmTable
from panda3d.core import PTAFloat, CPTAFloat, AnimBundleNode
from direct.actor.Actor import Actor

def getNodeFromController(controller, controlled_prim):
        if type(controlled_prim) is collada.controller.BoundSkinPrimitive:
            ch = Character('simplechar')
            bundle = ch.getBundle(0)
            skeleton = PartGroup(bundle, '<skeleton>')

            character_joints = {}
            for (name, joint_matrix) in controller.joint_matrices.iteritems():
                joint_matrix.shape = (-1)
                character_joints[name] = CharacterJoint(ch, bundle, skeleton, name, Mat4(*joint_matrix)) 
            
            tbtable = TransformBlendTable()
            
            for influence in controller.index:
                blend = TransformBlend()
                for (joint_index, weight_index) in influence:
                    char_joint = character_joints[controller.getJoint(joint_index)]
                    weight = controller.getWeight(weight_index)[0]
                    blend.addTransform(JointVertexTransform(char_joint), weight)
                tbtable.addBlend(blend)
                
            array = GeomVertexArrayFormat()
            array.addColumn(InternalName.make('vertex'), 3, Geom.NTFloat32, Geom.CPoint)
            array.addColumn(InternalName.make('normal'), 3, Geom.NTFloat32, Geom.CPoint)
            array.addColumn(InternalName.make('texcoord'), 2, Geom.NTFloat32, Geom.CTexcoord)
            blendarr = GeomVertexArrayFormat()
            blendarr.addColumn(InternalName.make('transform_blend'), 1, Geom.NTUint16, Geom.CIndex)
            
            format = GeomVertexFormat()
            format.addArray(array)
            format.addArray(blendarr)
            aspec = GeomVertexAnimationSpec()
            aspec.setPanda()
            format.setAnimation(aspec)
            format = GeomVertexFormat.registerFormat(format)
            
            dataname = controller.id + '-' + controlled_prim.primitive.material.id
            vdata = GeomVertexData(dataname, format, Geom.UHStatic)
            vertex = GeomVertexWriter(vdata, 'vertex')
            normal = GeomVertexWriter(vdata, 'normal')
            texcoord = GeomVertexWriter(vdata, 'texcoord')
            transform = GeomVertexWriter(vdata, 'transform_blend') 
            
            numtris = 0
            if type(controlled_prim.primitive) is collada.polylist.BoundPolylist:
                for poly in controlled_prim.primitive.polygons():
                    for tri in poly.triangles():
                        for tri_pt in range(3):
                            vertex.addData3f(tri.vertices[tri_pt][0], tri.vertices[tri_pt][1], tri.vertices[tri_pt][2])
                            normal.addData3f(tri.normals[tri_pt][0], tri.normals[tri_pt][1], tri.normals[tri_pt][2])
                            if len(controlled_prim.primitive._texcoordset) > 0:
                                texcoord.addData2f(tri.texcoords[0][tri_pt][0], tri.texcoords[0][tri_pt][1])
                            transform.addData1i(tri.indices[tri_pt])
                        numtris+=1
            elif type(controlled_prim.primitive) is collada.triangleset.BoundTriangleSet:
                for tri in controlled_prim.primitive.triangles():
                    for tri_pt in range(3):
                        vertex.addData3f(tri.vertices[tri_pt][0], tri.vertices[tri_pt][1], tri.vertices[tri_pt][2])
                        normal.addData3f(tri.normals[tri_pt][0], tri.normals[tri_pt][1], tri.normals[tri_pt][2])
                        if len(controlled_prim.primitive._texcoordset) > 0:
                            texcoord.addData2f(tri.texcoords[0][tri_pt][0], tri.texcoords[0][tri_pt][1])
                        transform.addData1i(tri.indices[tri_pt])
                    numtris+=1
                        
            tbtable.setRows(SparseArray.lowerOn(vdata.getNumRows())) 
            
            gprim = GeomTriangles(Geom.UHStatic)
            for i in range(numtris):
                gprim.addVertices(i*3, i*3+1, i*3+2)
                gprim.closePrimitive()
                
            pgeom = Geom(vdata)
            pgeom.addPrimitive(gprim)
            
            render_state = getStateFromMaterial(controlled_prim.primitive.material)
            control_node = GeomNode("ctrlnode")
            control_node.addGeom(pgeom, render_state)
            ch.addChild(control_node)
        
            bundle = AnimBundle('simplechar', 5.0, 2)
            skeleton = AnimGroup(bundle, '<skeleton>')
            root = AnimChannelMatrixXfmTable(skeleton, 'root')
            
            #hjoint = AnimChannelMatrixXfmTable(root, 'joint1') 
            #table = [10, 11, 12, 13, 14, 15, 14, 13, 12, 11] 
            #data = PTAFloat.emptyArray(len(table)) 
            #for i in range(len(table)): 
            #    data.setElement(i, table[i]) 
            #hjoint.setTable(ord('i'), CPTAFloat(data)) 
            
            #vjoint = AnimChannelMatrixXfmTable(hjoint, 'joint2') 
            #table = [10, 9, 8, 7, 6, 5, 6, 7, 8, 9] 
            #data = PTAFloat.emptyArray(len(table)) 
            #for i in range(len(table)): 
            #    data.setElement(i, table[i]) 
            #vjoint.setTable(ord('j'), CPTAFloat(data)) 

            wiggle = AnimBundleNode('wiggle', bundle)

            np = NodePath(ch) 
            anim = NodePath(wiggle) 
            a = Actor(np, {'simplechar' : anim})
            a.loop('simplechar') 
            return a
            #a.setPos(0, 0, 0)
        
        else:
            raise Exception("Error: unsupported controller type")

def getVertexData(vertex, vertex_index, normal=None, normal_index=None, texcoordset=(), texcoord_indexset=()):
        vertex_data = vertex[vertex_index]
        vertex_data.shape = (-1, 3)
        stacked = vertex_data
        if normal is not None:
            normal_data = normal[normal_index]
            normal_data.shape = (-1, 3)
            collada.util.normalize_v3(normal_data)
            stacked = numpy.hstack((stacked, normal_data))
        if len(texcoordset) > 0:
            texcoord_data = texcoordset[0][texcoord_indexset[0]]
            texcoord_data.shape = (-1, 2)
            stacked = numpy.hstack((stacked, texcoord_data))

        if normal is None and len(texcoordset) == 0:
            format = GeomVertexFormat.getV3() #just vertices
            stride = 12
        elif normal is not None and len(texcoordset) == 0:
            format = GeomVertexFormat.getV3n3() #vertices + normals
            stride = 24
        elif normal is None and len(texcoordset) > 0:
            format = GeomVertexFormat.getV3t2() #vertices + texcoords
            stride = 20
        else:
            format = GeomVertexFormat.getV3n3t2()
            stride = 32
            
        assert(stacked.shape[1]*4 == stride)

        stacked = stacked.flatten()
        stacked.shape = (-1)
        assert(stacked.dtype == numpy.float32)
        all_data = stacked.tostring()

        vdata = GeomVertexData("dataname", format, Geom.UHStatic)
        arr = GeomVertexArrayData(vdata.getArray(0).getArrayFormat(), GeomEnums.UHStream)
        datahandle = arr.modifyHandle()
        datahandle.setData(all_data)
        vdata.setArray(0, arr)
        
        return vdata

def getPrimAndDataFromTri(triset):
        if triset.normal is None:
            triset.generateNormals()

        vdata = getVertexData(triset.vertex, triset.vertex_index,
                              triset.normal, triset.normal_index,
                              triset.texcoordset, triset.texcoord_indexset)

        gprim = GeomTriangles(Geom.UHStatic)
        gprim.addConsecutiveVertices(0, 3*triset.ntriangles)
        gprim.closePrimitive()
        
        return (vdata, gprim)

def getNodeFromGeom(prim):
        if type(prim) is collada.triangleset.BoundTriangleSet:
            
            (vdata, gprim) = getPrimAndDataFromTri(prim)
            
        elif type(prim) is collada.polylist.BoundPolylist or \
            type(prim) is collada.polygons.BoundPolygons:
            
            triset = prim.triangleset()
            (vdata, gprim) = getPrimAndDataFromTri(triset)
            
        elif type(prim) is collada.lineset.BoundLineSet:
            
            vdata = getVertexData(prim.vertex, prim.vertex_index)           
            gprim = GeomLines(Geom.UHStatic)
            gprim.addConsecutiveVertices(0, 2*prim.nlines)
            gprim.closePrimitive()
            
        else:
            raise Exception("Error: Unsupported primitive type. Exiting.")
            
        pgeom = Geom(vdata)
        pgeom.addPrimitive(gprim)
        
        render_state = getStateFromMaterial(prim.material)
        node = GeomNode("primitive")
        node.addGeom(pgeom, render_state)
        
        return node

def getStateFromMaterial(prim_material):
    state = RenderState.makeFullDefault()
    
    mat = Material()
    
    if prim_material:
        for prop in prim_material.supported:
            value = getattr(prim_material, prop)
            if value is None:
                continue
            
            if type(value) is tuple:
                val4 = value[3] if len(value) > 3 else 1.0
                value = VBase4(value[0], value[1], value[2], val4)
            
            if isinstance(value, collada.material.Map):
                image_data = value.sampler.surface.image.data
                if image_data:
                    myImage = PNMImage()
                    myImage.read(StringStream(image_data), posixpath.basename(value.sampler.surface.image.path))
                    myTexture = Texture(value.sampler.surface.image.id)
                    myTexture.load(myImage)
                    state = state.addAttrib(TextureAttrib.make(myTexture))
            elif prop == 'emission':
                mat.setEmission(value)
            elif prop == 'ambient':
                mat.setAmbient(value)
            elif prop == 'diffuse':
                mat.setDiffuse(value)
            elif prop == 'specular':
                #mat.setSpecular(value)
                pass
            elif prop == 'shininess':
                mat.setShininess(value)
            elif prop == 'reflective':
                pass
            elif prop == 'reflectivity':
                pass
            elif prop == 'transparent':
                pass
            elif prop == 'transparency':
                pass

    state = state.addAttrib(MaterialAttrib.make(mat))
    return state

def setCameraAngle(ang):
    base.camera.setPos(20.0 * sin(ang), -20.0 * cos(ang), 0)
    base.camera.lookAt(0.0, 0.0, 0.0)

def spinCameraTask(task):
    speed = 5.0
    curSpot = task.time % speed
    angleDegrees = (curSpot / speed) * 360
    angleRadians = angleDegrees * (pi / 180.0)
    setCameraAngle(angleRadians)
    return Task.cont

def attachLights(render):
    ambientLight = AmbientLight('ambientLight')
    ambientLight.setColor(Vec4(0.1, 0.1, 0.1, 1))
    ambientLightNP = render.attachNewNode(ambientLight)
    render.setLight(ambientLightNP)
    
    directionalPoints = [(10,0,0), (-10,0,0),
                         (0,-10,0), (0,10,0),
                         (0, 0, -10), (0,0,10)]
    
    for pt in directionalPoints:
        directionalLight = DirectionalLight('directionalLight')
        directionalLight.setColor(Vec4(0.4, 0.4, 0.4, 1))
        directionalLightNP = render.attachNewNode(directionalLight)
        directionalLightNP.setPos(pt[0], pt[1], pt[2])
        directionalLightNP.lookAt(0,0,0)
        render.setLight(directionalLightNP)

def getBaseNodePath(render):
    globNode = GeomNode("collada")
    return render.attachNewNode(globNode)

def ensureCameraAt(nodePath, cam):
    boundingSphere = nodePath.getBounds()
    scale = 5.0 / boundingSphere.getRadius()
    
    nodePath.setScale(scale, scale, scale)
    boundingSphere = nodePath.getBounds()
    nodePath.setPos(-1 * boundingSphere.getCenter().getX(),
                    -1 * boundingSphere.getCenter().getY(),
                    -1 * boundingSphere.getCenter().getZ())
    nodePath.setHpr(0,0,0)
       
    cam.setPos(15, -15, 0)
    cam.lookAt(0.0, 0.0, 0.0)

def getNodesFromCollada(col):
    nodes = []
    for geom in col.scene.objects('geometry'):
        for prim in geom.primitives():
            if prim.vertex is not None and len(prim.vertex) > 0:
                node = getNodeFromGeom(prim)
                nodes.append(node)
    
    for controller in col.scene.objects('controller'):
        for controlled_prim in controller.primitives():
            for prim in controlled_prim.boundskin.geometry.primitives():
                if prim.vertex is not None and len(prim.vertex) > 0:
                    node = getNodeFromGeom(prim)
                    nodes.append(node)
    return nodes

def setupPandaApp(mesh):
    nodes = getNodesFromCollada(mesh)
    
    p3dApp = ShowBase()
    nodePath = getBaseNodePath(render)
    for node in nodes:
        nodePath.attachNewNode(node)
    ensureCameraAt(nodePath, base.camera)
    base.disableMouse()
    attachLights(render)
    return p3dApp

def getScreenshot(p3dApp):
    p3dApp.taskMgr.step()
    pnmss = PNMImage()
    p3dApp.win.getScreenshot(pnmss)
    resulting_ss = StringStream()
    pnmss.write(resulting_ss, "screenshot.png")
    screenshot_buffer = resulting_ss.getData()
    pilimage = Image.open(StringIO(screenshot_buffer))
    pilimage.load()
    #pnmimage will sometimes output as palette mode for 8-bit png so convert
    pilimage = pilimage.convert('RGBA')
    return pilimage