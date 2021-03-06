function scene=mesh2scene(M,CameraMatrix,ligthDirectional,ambiantLight,SizeH,SizeW,getSilhouette)

if nargin<7
    getSilhouette=true;
end
[P2D,depths]=camera_project(CameraMatrix,M.V);
M=mesh_normals_and_surfaces(M);
cameraCenter=-(CameraMatrix(1:3,1:3))\CameraMatrix(:,4);
if  getSilhouette
    M=mesh_silhouette_edges(M,cameraCenter);
end
luminosity=max(0,(-ligthDirectional*M.NormalsV))+ambiantLight;
colorsV=M.colors.*([1;1;1]*luminosity);
Ntri=M.nbF;

scene.ij=flipud(P2D);%fliping i and j coordinate because matlab is not consistent wit numpy
scene.colors=colorsV;
scene.depths=depths;
if  getSilhouette
    scene.edgeflags=flipud(M.edge_bool(M.Faces_edges'));% flipping to reflect flip on ij
end

scene.faces = uint32( M.F([1,3,2],:))-1;% changing order to reflect flip on ij
scene.faces_uv = scene.faces;
scene.uv=zeros(2,M.nbV);
scene.textured=logical(zeros(1,Ntri));
scene.shade=zeros(1,M.nbV);
scene.SizeH=SizeH;
scene.SizeW=SizeW;
scene.shaded=logical(zeros(1,Ntri));
scene.texture=zeros(3,10,10)  ;
