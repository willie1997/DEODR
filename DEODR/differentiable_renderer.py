import numpy as np
from . import differentiable_renderer_cython
import copy

class Scene2D():
    """this class is a simple class that contains a set of 2D vertices with associated depths and a list of faces that are triplets of vertices indexes"""
    def __init__(self, faces, faces_uv, ij, depths,textured, uv, shade, colors, shaded, edgeflags,image_H, image_W, nbColors, texture, background):        
        self.faces = faces
        self.faces_uv = faces_uv
        self.ij = ij
        self.depths = depths
        self.textured = textured
        self.uv = uv
        self.shade = shade
        self.colors = colors
        self.shaded = shaded
        self.edgeflags = edgeflags
        self.image_H = image_H
        self.image_W = image_W
        self.nbColors = nbColors
        self.texture =  texture
        self.background = background  
        self.faces = faces
        self.faces_uv = faces_uv
        
        # fields to store gradients  
        self.uv_b = np.zeros(self.uv.shape)
        self.ij_b = np.zeros(self.ij.shape)
        self.shade_b = np.zeros(self.shade.shape)
        self.colors_b = np.zeros(self.colors.shape)
        self.texture_b = np.zeros(self.texture.shape)        
        
    def clear_gradients(self):
        self.uv_b.fill(0)
        self.ij_b.fill(0)
        self.shade_b.fill(0)
        self.colors_b.fill(0)  
        self.texture_b.fill(0)         
        
    def render(self, sigma = 1, antialiaseError = False, Aobs = None):    
        Zbuffer = np.zeros((self.image_H, self.image_W)) 
        Abuffer = np.zeros((self.image_H, self.image_W, self.nbColors))        
        
        if antialiaseError:            
            ErrBuffer = np.sum((Aobs - self.background)**2, axis=2)                          
            differentiable_renderer_cython.renderScene(self, sigma, Abuffer, Zbuffer, antialiaseError, Aobs, ErrBuffer) 
                        
        else:  
            ErrBuffer = None
            differentiable_renderer_cython.renderScene(self, sigma, Abuffer, Zbuffer, antialiaseError, Aobs, ErrBuffer)             
        
        self.Buffers = (Abuffer, Zbuffer, ErrBuffer)
        return Abuffer, Zbuffer, ErrBuffer
        
    def render_backward(self, Abuffer_b = None, ErrBuffer_b= None, sigma = 1, antialiaseError = False, Aobs = None, make_copies=True):
        Abuffer, Zbuffer, ErrBuffer = self.Buffers
        if antialiaseError:       
            assert(Abuffer_b is None)
            if make_copies:
                differentiable_renderer_cython.renderSceneB(self, sigma, Abuffer, Zbuffer, None, antialiaseError, Aobs, ErrBuffer.copy(), ErrBuffer_b)
            else: # if we don't make copies the image Abuffer will 
                differentiable_renderer_cython.renderSceneB(self, sigma, Abuffer, Zbuffer, None, antialiaseError, Aobs, ErrBuffer, ErrBuffer_b)                       
        else:  
            assert(ErrBuffer_b is None)  
            assert(Aobs is None)  
            if make_copies: # if we make copies we keep the antialized image unchanged Abuffer along the occlusion boundaries
                differentiable_renderer_cython.renderSceneB(self, sigma, Abuffer.copy(), Zbuffer, Abuffer_b, antialiaseError, None, ErrBuffer, ErrBuffer_b)
            else:
                differentiable_renderer_cython.renderSceneB(self, sigma, Abuffer, Zbuffer, Abuffer_b, antialiaseError, None, ErrBuffer, ErrBuffer_b)
                   
            
    def render_compare_and_backward(self, sigma = 1, antialiaseError = False, Aobs=None, mask = None, clear_gradients = True, make_copies=True):        
        if mask is None:
            mask = np.ones((Aobs.shape[0],Aobs.shape[1]))   
        print('forward')
        Abuffer, Zbuffer, ErrBuffer = self.render(sigma, antialiaseError, Aobs)
        if clear_gradients:
            self.clear_gradients()   
            
        if antialiaseError:
            Abuffer_b= None
            ErrBuffer = ErrBuffer * mask    
            Err = np.sum(ErrBuffer)      
            ErrBuffer_b = copy.copy(mask)  
            
        else:        
            diffImage=(Abuffer - Aobs) * mask[:,:,None]
            ErrBuffer = (diffImage) **2
            Err = np.sum(ErrBuffer)    
            Abuffer_b = 2 * diffImage     
            ErrBuffer_b = None
            
        self.render_backward(Abuffer_b, ErrBuffer_b ,sigma,antialiaseError = antialiaseError, Aobs = Aobs ,make_copies = make_copies)  
        return  Abuffer, Zbuffer, ErrBuffer, Err

class Scene3D():
    def __init__(self):
        self.mesh = None
        self.ligthDirectional = None
        self.ambiantLight = None
        self.sigma = 1
        
        
    def clear_gradients(self):
    
        # fields to store gradients  
        self.uv_b = np.zeros((self.mesh.nbV,2))
        self.ij_b = np.zeros((self.mesh.nbV,2))
        self.shade_b = np.zeros((self.mesh.nbV))
        self.colors_b = np.zeros((self.mesh.nbV,3))
        self.texture_b =  np.zeros((0,0)) 
    
    def setLight(self, ligthDirectional, ambiantLight):  
        self.ligthDirectional = ligthDirectional
        self.ambiantLight = ambiantLight
        
    def setMesh(self,mesh):
        self.mesh = mesh
        
    def setBackground(self,backgroundImage):
        self.background = backgroundImage
    
    def cameraProject(self,cameraMatrix,P3D, get_jacobians = False) : 
        r = np.column_stack((P3D, np.ones((P3D.shape[0],1), dtype = np.double))).dot(cameraMatrix.T)
        depths = r[:,2]
        P2D = r[:,:2]/depths[:,None]
        if get_jacobians:
            J_r = cameraMatrix[:,:3]
            J_d = J_r[2,:]
            J_PD2 = (J_r[:2,:]*depths[:,None,None]-r[:,:2,None]*J_d)/((depths**2)[:,None,None])
            return P2D,depths,J_PD2
        else:           
            return P2D,depths 
        
    def projectionsJacobian(self,CameraMatrix, vertices):
        P2D,depths,J_P2D = self.camera_project(CameraMatrix, vertices, get_jacobians=True) 
        return J_P2D     
    
    def cameraProject_backward(self,cameraMatrix, P3D, P2D_b) :
        r = np.column_stack((P3D, np.ones((P3D.shape[0],1), dtype = np.double))).dot(cameraMatrix.T)
        depths = r[:,2]
        #P2D = r[:,:2]/depths[:,None]
        r_b = np.column_stack((P2D_b/depths[:,None], -np.sum(P2D_b*r[:,:2],axis=1)/(depths**2))) 
        P3D_b = r_b.dot(cameraMatrix[:,:3])
        return P3D_b        
        
    def computeVerticesColorsWithIllumination(self):
        directional = np.maximum(0,-np.sum(self.mesh.vertexNormals * self.ligthDirectional, axis = 1))
        verticesLuminosity = directional + self.ambiantLight
        colors = self.mesh.verticesColors * verticesLuminosity[:,None] 
        return colors 
    
    def computeVerticescolorsWithIllumination_backward(self, colors_b):
        directional = np.maximum(0,-np.sum(self.mesh.vertexNormals * self.ligthDirectional, axis = 1))
        verticesLuminosity = directional + self.ambiantLight
        
        verticesLuminosity_b = np.sum(self.mesh.verticesColors * colors_b,axis=1)
        self.mesh.verticesColors_b = colors_b * verticesLuminosity[:,None]
        self.ambiantLight_b = np.sum(verticesLuminosity_b)
        directional_b = verticesLuminosity_b 
        self.lightDirectional_b = -np.sum(((directional_b*(directional>0))[:,None]) * self.mesh.vertexNormals,axis=0)
        self.vertexNormals_b = -((directional_b*(directional>0))[:,None]) * self.ligthDirectional
    
    def render2D(self,ij,colors):   
        nbColorChanels = colors.shape[1]
        Abuffer = np.empty((self.image_H, self.image_W, nbColorChanels))
        Zbuffer = np.empty((self.image_H, self.image_W))
        self.ij = np.array (ij)#should automatically detached according to https://pytorch.org/docs/master/notes/extending.html
        self.colors = np.array (colors)  
        differentiable_renderer_cython.renderScene(self, self.sigma, Abuffer, Zbuffer) 
        self.Buffers = (Abuffer, Zbuffer)
        return Abuffer, Zbuffer
    
    def render2D_backward(self,Abuffer_b):  
        Abuffer,Zbuffer = self.Buffers
        differentiable_renderer_cython.renderSceneB(self, self.sigma, Abuffer.copy(), Zbuffer, Abuffer_b)  
        return self.ij_b, self.colors_b  
           
    def render(self,CameraMatrix,resolution):
        self.mesh.computeVertexNormals()
        
        ij,depths = self.cameraProject(CameraMatrix, self.mesh.vertices)        
        cameraCenter3D = -np.linalg.solve(CameraMatrix[:3,:3], CameraMatrix[:,3]) 
        colors =  self.computeVerticesColorsWithIllumination()
        
        #compute silhouette edges 
        edge_bool = self.mesh.edgeOnSilhouette(cameraCenter3D)
        
        # construct triangle soup  
        self.faces=self.mesh.faces.astype(np.uint32)
        self.faces_uv=self.faces         
        self.depths = depths  
        self.edgeflags = edge_bool
        self.uv = np.zeros((self.mesh.nbV,2))
        self.textured = np.zeros((self.mesh.nbF),dtype=np.bool)
        self.shade = np.zeros((self.mesh.nbV),dtype=np.bool) # eventually used when using texture
        self.image_H = resolution[1]
        self.image_W = resolution[0]
        self.shaded = np.zeros((self.mesh.nbF),dtype=np.bool) # eventually used when using texture
        self.texture = np.zeros((0,0))          
        Abuffer = self.render2D(ij,colors)
        return Abuffer    
    
    def render_backward(self,CameraMatrix, Abuffer_b):
        cameraCenter3D = -np.linalg.solve(CameraMatrix[:3,:3], CameraMatrix[:,3]) 
        ij_b, colors_b = self.render2D_backward(Abuffer_b)
        self.computeVerticescolorsWithIllumination_backward(colors_b)
        vertices_b = self.cameraProject_backward(CameraMatrix, self.mesh.vertices, ij_b)
        self.mesh.computeVertexNormals_backward(self.vertexNormals_b)
        

    def renderDepth(self,CameraMatrix,resolution,depth_scale):        
        P2D, depths = self.camera_project(CameraMatrix, self.mesh.vertices)        
        cameraCenter3D = -np.linalg.solve(CameraMatrix[:3,:3], CameraMatrix[:,3])        
    
        #compute silhouette edges 
        self.mesh.computeFaceNormals()
        edge_bool = self.mesh.edgeOnSilhouette(cameraCenter3D)
    
        # construct triangle soup        
        self.faces=self.mesh.faces.astype(np.uint32)
        self.faces_uv=self.faces
        ij = P2D
        colors = depths[:,None]*depth_scale
        self.depths = depths
        self.edgeflags = edge_bool
        self.uv = np.zeros((self.mesh.nbV,2))
        self.textured = np.zeros((self.mesh.nbF), dtype = np.bool)
        self.shade = np.zeros((self.mesh.nbV), dtype = np.bool) # eventually used when using texture
        self.image_H = resolution[1]
        self.image_W = resolution[0]
        self.shaded = np.zeros((self.mesh.nbF),dtype=np.bool) # eventually used when using texture
        self.texture = np.zeros((0,0))
        #colors[:,:,:]=1
        Abuffer = self.render2D(ij,colors)
        return Abuffer
    
    def renderDepth_backward():
        pass
    


