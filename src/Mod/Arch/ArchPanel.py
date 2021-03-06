#***************************************************************************
#*                                                                         *
#*   Copyright (c) 2011                                                    *
#*   Yorik van Havre <yorik@uncreated.net>                                 *
#*                                                                         *
#*   This program is free software; you can redistribute it and/or modify  *
#*   it under the terms of the GNU Lesser General Public License (LGPL)    *
#*   as published by the Free Software Foundation; either version 2 of     *
#*   the License, or (at your option) any later version.                   *
#*   for detail see the LICENCE text file.                                 *
#*                                                                         *
#*   This program is distributed in the hope that it will be useful,       *
#*   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
#*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
#*   GNU Library General Public License for more details.                  *
#*                                                                         *
#*   You should have received a copy of the GNU Library General Public     *
#*   License along with this program; if not, write to the Free Software   *
#*   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
#*   USA                                                                   *
#*                                                                         *
#***************************************************************************

import FreeCAD,Draft,ArchComponent,DraftVecUtils,ArchCommands,math, Part
from FreeCAD import Vector
if FreeCAD.GuiUp:
    import FreeCADGui
    from PySide import QtCore, QtGui
    from DraftTools import translate
    from PySide.QtCore import QT_TRANSLATE_NOOP
else:
    # \cond
    def translate(ctxt,txt):
        return txt
    def QT_TRANSLATE_NOOP(ctxt,txt):
        return txt
    # \endcond

## @package ArchPanel
#  \ingroup ARCH
#  \brief The Panel object and tools
#
#  This module provides tools to build Panel objects.
#  Panels consist of a closed shape that gets extruded to
#  produce a flat object.


__title__="FreeCAD Panel"
__author__ = "Yorik van Havre"
__url__ = "http://www.freecadweb.org"

#           Description                 l    w    t

Presets = [None,
           ["Plywood 12mm, 1220 x 2440",1200,2400,12],
           ["Plywood 15mm, 1220 x 2440",1200,2400,15],
           ["Plywood 18mm, 1220 x 2440",1200,2400,18],
           ["Plywood 25mm, 1220 x 2440",1200,2400,25],
           ["MDF 3mm, 900 x 600",       900, 600, 3],
           ["MDF 6mm, 900 x 600",       900, 600, 6],
           ["OSB 18mm, 1200 x 2400",    1200,2400,18]]

def makePanel(baseobj=None,length=0,width=0,thickness=0,placement=None,name="Panel"):
    '''makePanel([obj],[length],[width],[thickness],[placement]): creates a
    panel element based on the given profile object and the given
    extrusion thickness. If no base object is given, you can also specify
    length and width for a simple cubic object.'''
    obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython",name)
    obj.Label = translate("Arch",name)
    _Panel(obj)
    if FreeCAD.GuiUp:
        _ViewProviderPanel(obj.ViewObject)
    if baseobj:
        obj.Base = baseobj
        obj.Base.ViewObject.hide()
    if width:
        obj.Width = width
    if thickness:
        obj.Thickness = thickness
    if length:
        obj.Length = length
    return obj


def makePanelView(panel,page=None,name="PanelView"):
    """makePanelView(panel,[page]) : Creates a Drawing view of the given panel
    in the given or active Page object (a new page will be created if none exists)."""
    if not page:
        for o in FreeCAD.ActiveDocument.Objects:
            if o.isDerivedFrom("Drawing::FeaturePage"):
                page = o
                break
        if not page:
            page = FreeCAD.ActiveDocument.addObject("Drawing::FeaturePage",translate("Arch","Page"))
            page.Template = Draft.getParam("template",FreeCAD.getResourceDir()+'Mod/Drawing/Templates/A3_Landscape.svg')
    view = FreeCAD.ActiveDocument.addObject("Drawing::FeatureViewPython",name)
    page.addObject(view)
    PanelView(view)
    view.Source = panel
    view.Label = translate("Arch","View of")+" "+panel.Label
    return view


def makePanelCut(panel,name="PanelView"):
    """makePanelCut(panel) : Creates a 2D view of the given panel
    in the 3D space, positioned at the origin."""
    view = FreeCAD.ActiveDocument.addObject("Part::FeaturePython",name)
    PanelCut(view)
    view.Source = panel
    view.Label = translate("Arch","View of")+" "+panel.Label
    if FreeCAD.GuiUp:
        ViewProviderPanelCut(view.ViewObject)
    return view


def makePanelSheet(panels=[],name="PanelSheet"):
    """makePanelSheet([panels]) : Creates a sheet with the given panel cuts
    in the 3D space, positioned at the origin."""
    sheet = FreeCAD.ActiveDocument.addObject("Part::FeaturePython",name)
    PanelSheet(sheet)
    if panels:
        sheet.Group = panels
    if FreeCAD.GuiUp:
        ViewProviderPanelSheet(sheet.ViewObject)
    return sheet


class CommandPanel:
    "the Arch Panel command definition"
    def GetResources(self):
        return {'Pixmap'  : 'Arch_Panel',
                'MenuText': QT_TRANSLATE_NOOP("Arch_Panel","Panel"),
                'Accel': "P, A",
                'ToolTip': QT_TRANSLATE_NOOP("Arch_Panel","Creates a panel object from scratch or from a selected object (sketch, wire, face or solid)")}

    def IsActive(self):
        return not FreeCAD.ActiveDocument is None

    def Activated(self):
        p = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Arch")
        self.Length = p.GetFloat("PanelLength",1000)
        self.Width = p.GetFloat("PanelWidth",1000)
        self.Thickness = p.GetFloat("PanelThickness",10)
        self.Profile = None
        self.continueCmd = False
        self.rotated = False
        sel = FreeCADGui.Selection.getSelection()
        if sel:
            if len(sel) == 1:
                if Draft.getType(sel[0]) == "Panel":
                    return
            FreeCAD.ActiveDocument.openTransaction(str(translate("Arch","Create Panel")))
            FreeCADGui.addModule("Arch")
            FreeCADGui.addModule("Draft")
            for obj in sel:
                FreeCADGui.doCommand("obj = Arch.makePanel(FreeCAD.ActiveDocument." + obj.Name + ",thickness=" + str(self.Thickness) + ")")
                FreeCADGui.doCommand("Draft.autogroup(obj)")
            FreeCAD.ActiveDocument.commitTransaction()
            FreeCAD.ActiveDocument.recompute()
            return

        # interactive mode
        if hasattr(FreeCAD,"DraftWorkingPlane"):
            FreeCAD.DraftWorkingPlane.setup()
        import DraftTrackers
        self.points = []
        self.tracker = DraftTrackers.boxTracker()
        self.tracker.width(self.Width)
        self.tracker.height(self.Thickness)
        self.tracker.length(self.Length)
        self.tracker.on()
        FreeCADGui.Snapper.getPoint(callback=self.getPoint,movecallback=self.update,extradlg=self.taskbox())

    def getPoint(self,point=None,obj=None):
        "this function is called by the snapper when it has a 3D point"
        self.tracker.finalize()
        if point == None:
            return
        FreeCAD.ActiveDocument.openTransaction(str(translate("Arch","Create Panel")))
        FreeCADGui.addModule("Arch")
        if self.Profile:
            pr = Presets[self.Profile]
            FreeCADGui.doCommand('p = Arch.makeProfile('+str(pr[2])+','+str(pr[3])+','+str(pr[4])+','+str(pr[5])+')')
            FreeCADGui.doCommand('s = Arch.makePanel(p,thickness='+str(self.Thickness)+')')
            #FreeCADGui.doCommand('s.Placement.Rotation = FreeCAD.Rotation(-0.5,0.5,-0.5,0.5)')
        else:
            FreeCADGui.doCommand('s = Arch.makePanel(length='+str(self.Length)+',width='+str(self.Width)+',thickness='+str(self.Thickness)+')')
        FreeCADGui.doCommand('s.Placement.Base = '+DraftVecUtils.toString(point))
        if self.rotated:
            FreeCADGui.doCommand('s.Placement.Rotation = FreeCAD.Rotation(FreeCAD.Vector(1.00,0.00,0.00),90.00)')
        FreeCAD.ActiveDocument.commitTransaction()
        FreeCAD.ActiveDocument.recompute()
        if self.continueCmd:
            self.Activated()

    def taskbox(self):
        "sets up a taskbox widget"
        w = QtGui.QWidget()
        ui = FreeCADGui.UiLoader()
        w.setWindowTitle(translate("Arch","Panel options", utf8_decode=True))
        grid = QtGui.QGridLayout(w)

        # presets box
        labelp = QtGui.QLabel(translate("Arch","Preset", utf8_decode=True))
        valuep = QtGui.QComboBox()
        fpresets = [" "]
        for p in Presets[1:]:
            fpresets.append(translate("Arch",p[0]))
        valuep.addItems(fpresets)
        grid.addWidget(labelp,0,0,1,1)
        grid.addWidget(valuep,0,1,1,1)

        # length
        label1 = QtGui.QLabel(translate("Arch","Length", utf8_decode=True))
        self.vLength = ui.createWidget("Gui::InputField")
        self.vLength.setText(FreeCAD.Units.Quantity(self.Length,FreeCAD.Units.Length).UserString)
        grid.addWidget(label1,1,0,1,1)
        grid.addWidget(self.vLength,1,1,1,1)

        # width
        label2 = QtGui.QLabel(translate("Arch","Width", utf8_decode=True))
        self.vWidth = ui.createWidget("Gui::InputField")
        self.vWidth.setText(FreeCAD.Units.Quantity(self.Width,FreeCAD.Units.Length).UserString)
        grid.addWidget(label2,2,0,1,1)
        grid.addWidget(self.vWidth,2,1,1,1)

        # height
        label3 = QtGui.QLabel(translate("Arch","Thickness", utf8_decode=True))
        self.vHeight = ui.createWidget("Gui::InputField")
        self.vHeight.setText(FreeCAD.Units.Quantity(self.Thickness,FreeCAD.Units.Length).UserString)
        grid.addWidget(label3,3,0,1,1)
        grid.addWidget(self.vHeight,3,1,1,1)

        # horizontal button
        value5 = QtGui.QPushButton(translate("Arch","Rotate", utf8_decode=True))
        grid.addWidget(value5,4,0,1,2)

        # continue button
        label4 = QtGui.QLabel(translate("Arch","Con&tinue", utf8_decode=True))
        value4 = QtGui.QCheckBox()
        value4.setObjectName("ContinueCmd")
        value4.setLayoutDirection(QtCore.Qt.RightToLeft)
        label4.setBuddy(value4)
        if hasattr(FreeCADGui,"draftToolBar"):
            value4.setChecked(FreeCADGui.draftToolBar.continueMode)
            self.continueCmd = FreeCADGui.draftToolBar.continueMode
        grid.addWidget(label4,5,0,1,1)
        grid.addWidget(value4,5,1,1,1)

        QtCore.QObject.connect(valuep,QtCore.SIGNAL("currentIndexChanged(int)"),self.setPreset)
        QtCore.QObject.connect(self.vLength,QtCore.SIGNAL("valueChanged(double)"),self.setLength)
        QtCore.QObject.connect(self.vWidth,QtCore.SIGNAL("valueChanged(double)"),self.setWidth)
        QtCore.QObject.connect(self.vHeight,QtCore.SIGNAL("valueChanged(double)"),self.setThickness)
        QtCore.QObject.connect(value4,QtCore.SIGNAL("stateChanged(int)"),self.setContinue)
        QtCore.QObject.connect(value5,QtCore.SIGNAL("pressed()"),self.rotate)
        return w

    def update(self,point,info):
        "this function is called by the Snapper when the mouse is moved"
        if FreeCADGui.Control.activeDialog():
            self.tracker.pos(point)
            if self.rotated:
                self.tracker.width(self.Thickness)
                self.tracker.height(self.Width)
                self.tracker.length(self.Length)
            else:
                self.tracker.width(self.Width)
                self.tracker.height(self.Thickness)
                self.tracker.length(self.Length)

    def setWidth(self,d):
        self.Width = d

    def setThickness(self,d):
        self.Thickness = d

    def setLength(self,d):
        self.Length = d

    def setContinue(self,i):
        self.continueCmd = bool(i)
        if hasattr(FreeCADGui,"draftToolBar"):
            FreeCADGui.draftToolBar.continueMode = bool(i)

    def setPreset(self,i):
        if i > 0:
            self.vLength.setText(FreeCAD.Units.Quantity(float(Presets[i][1]),FreeCAD.Units.Length).UserString)
            self.vWidth.setText(FreeCAD.Units.Quantity(float(Presets[i][2]),FreeCAD.Units.Length).UserString)
            self.vHeight.setText(FreeCAD.Units.Quantity(float(Presets[i][3]),FreeCAD.Units.Length).UserString)

    def rotate(self):
        self.rotated = not self.rotated


class CommandPanelCut:
    "the Arch Panel Cut command definition"
    def GetResources(self):
        return {'Pixmap'  : 'Arch_Panel_Cut',
                'MenuText': QT_TRANSLATE_NOOP("Arch_Panel_Cut","Panel Cut"),
                'Accel': "P, C",
                'ToolTip': QT_TRANSLATE_NOOP("Arch_Panel_Sheet","Creates 2D views of selected panels")}

    def IsActive(self):
        return not FreeCAD.ActiveDocument is None

    def Activated(self):
        if FreeCADGui.Selection.getSelection():
            FreeCAD.ActiveDocument.openTransaction(str(translate("Arch","Create Panel Cut")))
            FreeCADGui.addModule("Arch")
            for obj in FreeCADGui.Selection.getSelection():
                if Draft.getType(obj) == "Panel":
                    FreeCADGui.doCommand("Arch.makePanelCut(FreeCAD.ActiveDocument."+obj.Name+")")
            FreeCAD.ActiveDocument.commitTransaction()
            FreeCAD.ActiveDocument.recompute()


class CommandPanelSheet:
    "the Arch Panel Sheet command definition"
    def GetResources(self):
        return {'Pixmap'  : 'Arch_Panel_Sheet',
                'MenuText': QT_TRANSLATE_NOOP("Arch_Panel_Sheet","Panel Sheet"),
                'Accel': "P, S",
                'ToolTip': QT_TRANSLATE_NOOP("Arch_Panel_Sheet","Creates a 2D sheet which can contain panel cuts")}

    def IsActive(self):
        return not FreeCAD.ActiveDocument is None

    def Activated(self):
        FreeCAD.ActiveDocument.openTransaction(str(translate("Arch","Create Panel Sheet")))
        FreeCADGui.addModule("Arch")
        if FreeCADGui.Selection.getSelection():
            l = "["
            for obj in FreeCADGui.Selection.getSelection():
                l += "FreeCAD.ActiveDocument."+obj.Name+","
            l += "]"
            FreeCAD.ActiveDocument.commitTransaction()
            FreeCAD.ActiveDocument.recompute()
            FreeCADGui.doCommand("__objs__ = "+l)
            FreeCADGui.doCommand("Arch.makePanelSheet(__objs__)")
            FreeCADGui.doCommand("del __objs__")
        else:
            FreeCADGui.doCommand("Arch.makePanelSheet()")
        FreeCAD.ActiveDocument.commitTransaction()
        FreeCAD.ActiveDocument.recompute()



class _Panel(ArchComponent.Component):
    "The Panel object"
    def __init__(self,obj):
        ArchComponent.Component.__init__(self,obj)
        obj.addProperty("App::PropertyLength","Length","Arch",   QT_TRANSLATE_NOOP("App::Property","The length of this element, if not based on a profile"))
        obj.addProperty("App::PropertyLength","Width","Arch",    QT_TRANSLATE_NOOP("App::Property","The width of this element, if not based on a profile"))
        obj.addProperty("App::PropertyLength","Thickness","Arch",QT_TRANSLATE_NOOP("App::Property","The thickness or extrusion depth of this element"))
        obj.addProperty("App::PropertyInteger","Sheets","Arch",  QT_TRANSLATE_NOOP("App::Property","The number of sheets to use"))
        obj.addProperty("App::PropertyDistance","Offset","Arch",   QT_TRANSLATE_NOOP("App::Property","The offset between this panel and its baseline"))
        obj.addProperty("App::PropertyLength","WaveLength","Arch", QT_TRANSLATE_NOOP("App::Property","The length of waves for corrugated elements"))
        obj.addProperty("App::PropertyLength","WaveHeight","Arch", QT_TRANSLATE_NOOP("App::Property","The height of waves for corrugated elements"))
        obj.addProperty("App::PropertyAngle","WaveDirection","Arch", QT_TRANSLATE_NOOP("App::Property","The direction of waves for corrugated elements"))
        obj.addProperty("App::PropertyEnumeration","WaveType","Arch", QT_TRANSLATE_NOOP("App::Property","The type of waves for corrugated elements"))
        obj.addProperty("App::PropertyArea","Area","Arch",       QT_TRANSLATE_NOOP("App::Property","The area of this panel"))
        obj.addProperty("App::PropertyEnumeration","FaceMaker","Arch",QT_TRANSLATE_NOOP("App::Property","The facemaker type to use to build the profile of this object"))
        obj.addProperty("App::PropertyVector","Normal","Arch",QT_TRANSLATE_NOOP("App::Property","The normal extrusion direction of this object (keep (0,0,0) for automatic normal)"))
        obj.Sheets = 1
        self.Type = "Panel"
        obj.WaveType = ["Curved","Trapezoidal"]
        obj.FaceMaker = ["None","Simple","Cheese","Bullseye"]
        obj.setEditorMode("VerticalArea",2)
        obj.setEditorMode("HorizontalArea",2)

    def execute(self,obj):
        "creates the panel shape"

        if self.clone(obj):
            return

        import Part #, DraftGeomUtils

        # base tests
        if obj.Base:
            if obj.Base.isDerivedFrom("Part::Feature"):
                if obj.Base.Shape.isNull():
                    return
            elif obj.Base.isDerivedFrom("Mesh::Feature"):
                if not obj.Base.Mesh.isSolid():
                    return
        else:
            if obj.Length.Value:
                length = obj.Length.Value
            else:
                return
            if obj.Width.Value:
                width = obj.Width.Value
            else:
                return
        if obj.Thickness.Value:
            thickness = obj.Thickness.Value
        else:
            if not obj.Base:
                return
            elif obj.Base.isDerivedFrom("Part::Feature"):
                if not obj.Base.Shape.Solids:
                    return
        layers = []
        if hasattr(obj,"Material"):
            if obj.Material:
                if hasattr(obj.Material,"Materials"):
                    varwidth = 0
                    restwidth = thickness - sum(obj.Material.Thicknesses)
                    if restwidth > 0:
                        varwidth = [t for t in obj.Material.Thicknesses if t == 0]
                        if varwidth:
                            varwidth = restwidth/len(varwidth)
                    for t in obj.Material.Thicknesses:
                        if t:
                            layers.append(t)
                        elif varwidth:
                            layers.append(varwidth)
        # creating base shape
        pl = obj.Placement
        base = None
        normal = None
        if hasattr(obj,"Normal"):
            if obj.Normal.Length > 0:
                normal = Vector(obj.Normal)
                normal.normalize()
                normal.multiply(thickness)
        baseprofile = None
        if obj.Base:
            base = obj.Base.Shape.copy()
            if not base.Solids:
               # p = FreeCAD.Placement(obj.Base.Placement)
                if base.Faces:
                    baseprofile = base
                    if not normal:
                        normal = baseprofile.Faces[0].normalAt(0,0).multiply(thickness)
                    if layers:
                        layeroffset = 0
                        shps = []
                        for l in layers:
                            n = Vector(normal).normalize().multiply(l)
                            b = base.extrude(n)
                            if layeroffset:
                                o = Vector(normal).normalize().multiply(layeroffset)
                                b.translate(o)
                            shps.append(b)
                            layeroffset += l
                        base = Part.makeCompound(shps)
                    else:
                        base = base.extrude(normal)
                elif base.Wires:
                    fm = False
                    if hasattr(obj,"FaceMaker"):
                        if obj.FaceMaker != "None":
                            try:
                                baseprofile = Part.makeFace(base.Wires,"Part::FaceMaker"+str(obj.FaceMaker))
                                fm = True
                            except:
                                FreeCAD.Console.PrintError(translate("Arch","Facemaker returned an error")+"\n")
                                return
                    if not fm:
                        closed = True
                        for w in base.Wires:
                            if not w.isClosed():
                                closed = False
                        if closed:
                            baseprofile = ArchCommands.makeFace(base.Wires)
                    if not normal:
                        normal = baseprofile.normalAt(0,0).multiply(thickness)
                    if layers:
                        layeroffset = 0
                        shps = []
                        for l in layers:
                            n = Vector(normal).normalize().multiply(l)
                            b = baseprofile.extrude(n)
                            if layeroffset:
                                o = Vector(normal).normalize().multiply(layeroffset)
                                b.translate(o)
                            shps.append(b)
                            layeroffset += l
                        base = Part.makeCompound(shps)
                    else:
                        base = baseprofile.extrude(normal)
                elif obj.Base.isDerivedFrom("Mesh::Feature"):
                    if obj.Base.Mesh.isSolid():
                        if obj.Base.Mesh.countComponents() == 1:
                            sh = ArchCommands.getShapeFromMesh(obj.Base.Mesh)
                            if sh.isClosed() and sh.isValid() and sh.Solids:
                                base = sh
        else:
            if layers:
                shps = []
                layeroffset = 0
                for l in layers:
                    if normal:
                        n = Vector(normal).normalize().multiply(l)
                    else:
                        n = Vector(0,0,1).multiply(l)
                    l2 = length/2 or 0.5
                    w2 = width/2 or 0.5
                    v1 = Vector(-l2,-w2,layeroffset)
                    v2 = Vector(l2,-w2,layeroffset)
                    v3 = Vector(l2,w2,layeroffset)
                    v4 = Vector(-l2,w2,layeroffset)
                    base = Part.makePolygon([v1,v2,v3,v4,v1])
                    basepofile = Part.Face(base)
                    base = baseprofile.extrude(n)
                    shps.append(base)
                    layeroffset += l
                base = Part.makeCompound(shps)
            else:
                if not normal:
                    normal = Vector(0,0,1).multiply(thickness)
                l2 = length/2 or 0.5
                w2 = width/2 or 0.5
                v1 = Vector(-l2,-w2,0)
                v2 = Vector(l2,-w2,0)
                v3 = Vector(l2,w2,0)
                v4 = Vector(-l2,w2,0)
                base = Part.makePolygon([v1,v2,v3,v4,v1])
                baseprofile = Part.Face(base)
                base = baseprofile.extrude(normal)

        if hasattr(obj,"Area"):
            if baseprofile:
                obj.Area = baseprofile.Area

        if hasattr(obj,"WaveLength"):
            if baseprofile and obj.WaveLength.Value and obj.WaveHeight.Value:
                # corrugated element
                bb = baseprofile.BoundBox
                bb.enlarge(bb.DiagonalLength)
                p1 = Vector(bb.getPoint(0).x,bb.getPoint(0).y,bb.Center.z)
                if obj.WaveType == "Curved":
                    p2 = p1.add(Vector(obj.WaveLength.Value/2,0,obj.WaveHeight.Value))
                    p3 = p2.add(Vector(obj.WaveLength.Value/2,0,-obj.WaveHeight.Value))
                    e1 = Part.Arc(p1,p2,p3).toShape()
                    p4 = p3.add(Vector(obj.WaveLength.Value/2,0,-obj.WaveHeight.Value))
                    p5 = p4.add(Vector(obj.WaveLength.Value/2,0,obj.WaveHeight.Value))
                    e2 = Part.Arc(p3,p4,p5).toShape()
                else:
                    if obj.WaveHeight.Value < obj.WaveLength.Value:
                        p2 = p1.add(Vector(obj.WaveHeight.Value,0,obj.WaveHeight.Value))
                        p3 = p2.add(Vector(obj.WaveLength.Value-2*obj.WaveHeight.Value,0,0))
                        p4 = p3.add(Vector(obj.WaveHeight.Value,0,-obj.WaveHeight.Value))
                        e1 = Part.makePolygon([p1,p2,p3,p4])
                        p5 = p4.add(Vector(obj.WaveHeight.Value,0,-obj.WaveHeight.Value))
                        p6 = p5.add(Vector(obj.WaveLength.Value-2*obj.WaveHeight.Value,0,0))
                        p7 = p6.add(Vector(obj.WaveHeight.Value,0,obj.WaveHeight.Value))
                        e2 = Part.makePolygon([p4,p5,p6,p7])
                    else:
                        p2 = p1.add(Vector(obj.WaveLength.Value/2,0,obj.WaveHeight.Value))
                        p3 = p2.add(Vector(obj.WaveLength.Value/2,0,-obj.WaveHeight.Value))
                        e1 = Part.makePolygon([p1,p2,p3])
                        p4 = p3.add(Vector(obj.WaveLength.Value/2,0,-obj.WaveHeight.Value))
                        p5 = p4.add(Vector(obj.WaveLength.Value/2,0,obj.WaveHeight.Value))
                        e2 = Part.makePolygon([p3,p4,p5])
                edges = [e1,e2]
                for i in range(int(bb.XLength/(obj.WaveLength.Value*2))):
                    e1 = e1.copy()
                    e1.translate(Vector(obj.WaveLength.Value*2,0,0))
                    e2 = e2.copy()
                    e2.translate(Vector(obj.WaveLength.Value*2,0,0))
                    edges.extend([e1,e2])
                basewire = Part.Wire(edges)
                baseface = basewire.extrude(Vector(0,bb.YLength,0))
                base = baseface.extrude(Vector(0,0,thickness))
                rot = FreeCAD.Rotation(FreeCAD.Vector(0,0,1),normal)
                base.rotate(bb.Center,rot.Axis,math.degrees(rot.Angle))
                if obj.WaveDirection.Value:
                    base.rotate(bb.Center,normal,obj.WaveDirection.Value)
                n1 = normal.negative().normalize().multiply(obj.WaveHeight.Value*2)
                self.vol = baseprofile.copy()
                self.vol.translate(n1)
                self.vol = self.vol.extrude(n1.negative().multiply(2))
                base = self.vol.common(base)
                base = base.removeSplitter()
                if not base:
                    FreeCAD.Console.PrintError(translate("Arch","Error computing shape of ")+obj.Label+"\n")
                    return False

        if base and (obj.Sheets > 1) and normal and thickness:
            bases = [base]
            for i in range(1,obj.Sheets):
                n = FreeCAD.Vector(normal).normalize().multiply(i*thickness)
                b = base.copy()
                b.translate(n)
                bases.append(b)
            base = Part.makeCompound(bases)

        if base and normal and hasattr(obj,"Offset"):
            if obj.Offset.Value:
                v = DraftVecUtils.scaleTo(normal,obj.Offset.Value)
                base.translate(v)

        # process subshapes
        base = self.processSubShapes(obj,base,pl)

        # applying
        if base:
            if not base.isNull():
                if base.isValid() and base.Solids:
                    if len(base.Solids) == 1:
                        if base.Volume < 0:
                            base.reverse()
                        if base.Volume < 0:
                            FreeCAD.Console.PrintError(translate("Arch","Couldn't compute a shape"))
                            return
                        base = base.removeSplitter()
                    obj.Shape = base
                    if not pl.isNull():
                        obj.Placement = pl


class _ViewProviderPanel(ArchComponent.ViewProviderComponent):
    "A View Provider for the Panel object"

    def __init__(self,vobj):
        ArchComponent.ViewProviderComponent.__init__(self,vobj)
        vobj.ShapeColor = ArchCommands.getDefaultColor("Panel")

    def getIcon(self):
        #import Arch_rc
        if hasattr(self,"Object"):
            if hasattr(self.Object,"CloneOf"):
                if self.Object.CloneOf:
                    return ":/icons/Arch_Panel_Clone.svg"
        return ":/icons/Arch_Panel_Tree.svg"

    def updateData(self,obj,prop):
        if prop in ["Placement","Shape"]:
            if hasattr(obj,"Material"):
                if obj.Material:
                    if hasattr(obj.Material,"Materials"):
                        if len(obj.Material.Materials) == len(obj.Shape.Solids):
                            cols = []
                            for i,mat in enumerate(obj.Material.Materials):
                                c = obj.ViewObject.ShapeColor
                                c = (c[0],c[1],c[2],obj.ViewObject.Transparency/100.0)
                                if 'DiffuseColor' in mat.Material:
                                    if "(" in mat.Material['DiffuseColor']:
                                        c = tuple([float(f) for f in mat.Material['DiffuseColor'].strip("()").split(",")])
                                if 'Transparency' in mat.Material:
                                    c = (c[0],c[1],c[2],float(mat.Material['Transparency']))
                                cols.extend([c for j in range(len(obj.Shape.Solids[i].Faces))])
                            if obj.ViewObject.DiffuseColor != cols:
                                obj.ViewObject.DiffuseColor = cols
        ArchComponent.ViewProviderComponent.updateData(self,obj,prop)


class PanelView:
    "A Drawing view for Arch Panels"

    def __init__(self, obj):
        obj.addProperty("App::PropertyLink","Source","Base",QT_TRANSLATE_NOOP("App::Property","The linked object"))
        obj.addProperty("App::PropertyFloat","LineWidth","Drawing view",QT_TRANSLATE_NOOP("App::Property","The line width of the rendered objects"))
        obj.addProperty("App::PropertyColor","LineColor","Drawing view",QT_TRANSLATE_NOOP("App::Property","The color of the panel outline"))
        obj.addProperty("App::PropertyLength","FontSize","Tag view",QT_TRANSLATE_NOOP("App::Property","The size of the tag text"))
        obj.addProperty("App::PropertyColor","TextColor","Tag view",QT_TRANSLATE_NOOP("App::Property","The color of the tag text"))
        obj.addProperty("App::PropertyFloat","TextX","Tag view",QT_TRANSLATE_NOOP("App::Property","The X offset of the tag text"))
        obj.addProperty("App::PropertyFloat","TextY","Tag view",QT_TRANSLATE_NOOP("App::Property","The Y offset of the tag text"))
        obj.addProperty("App::PropertyString","FontName","Tag view",QT_TRANSLATE_NOOP("App::Property","The font of the tag text"))
        obj.Proxy = self
        self.Type = "PanelView"
        obj.LineWidth = 0.35
        obj.LineColor = (0.0,0.0,0.0)
        obj.TextColor = (0.0,0.0,1.0)
        obj.X = 10
        obj.Y = 10
        obj.TextX = 10
        obj.TextY = 10
        obj.FontName = "sans"

    def execute(self, obj):
        if obj.Source:
            if hasattr(obj.Source.Proxy,"BaseProfile"):
                p = obj.Source.Proxy.BaseProfile
                n = obj.Source.Proxy.ExtrusionVector
                import Drawing
                svg1 = ""
                svg2 = ""
                result = ""
                svg1 = Drawing.projectToSVG(p,DraftVecUtils.neg(n))
                if svg1:
                    w = str(obj.LineWidth/obj.Scale) #don't let linewidth be influenced by the scale...
                    svg1 = svg1.replace('stroke-width="0.35"','stroke-width="'+w+'"')
                    svg1 = svg1.replace('stroke-width="1"','stroke-width="'+w+'"')
                    svg1 = svg1.replace('stroke-width:0.01','stroke-width:'+w)
                    svg1 = svg1.replace('scale(1,-1)','scale('+str(obj.Scale)+',-'+str(obj.Scale)+')')
                if obj.Source.Tag:
                    svg2 = '<text id="tag'+obj.Name+'"'
                    svg2 += ' fill="'+Draft.getrgb(obj.TextColor)+'"'
                    svg2 += ' font-size="'+str(obj.FontSize)+'"'
                    svg2 += ' style="text-anchor:start;text-align:left;'
                    svg2 += ' font-family:'+obj.FontName+'" '
                    svg2 += ' transform="translate(' + str(obj.TextX) + ',' + str(obj.TextY) + ')">'
                    svg2 += '<tspan>'+obj.Source.Tag+'</tspan></text>\n'
                result += '<g id="' + obj.Name + '"'
                result += ' transform="'
                result += 'rotate('+str(obj.Rotation)+','+str(obj.X)+','+str(obj.Y)+') '
                result += 'translate('+str(obj.X)+','+str(obj.Y)+')'
                result += '">\n  '
                result += svg1
                result += svg2
                result += '</g>'
                obj.ViewResult = result

    def onChanged(self, obj, prop):
        pass

    def __getstate__(self):
        return self.Type

    def __setstate__(self,state):
        if state:
            self.Type = state

    def getDisplayModes(self,vobj):
        modes=["Default"]
        return modes

    def setDisplayMode(self,mode):
        return mode


class PanelCut(Draft._DraftObject):
    "A flat, 2D view of an Arch Panel"

    def __init__(self, obj):
        Draft._DraftObject.__init__(self,obj)
        obj.addProperty("App::PropertyLink","Source","Arch",QT_TRANSLATE_NOOP("App::Property","The linked object"))
        obj.addProperty("App::PropertyString","TagText","Arch",QT_TRANSLATE_NOOP("App::Property","The text to display. Can be %tag%, %label% or %description% to display the panel tag or label"))
        obj.addProperty("App::PropertyLength","TagSize","Arch",QT_TRANSLATE_NOOP("App::Property","The size of the tag text"))
        obj.addProperty("App::PropertyVector","TagPosition","Arch",QT_TRANSLATE_NOOP("App::Property","The position of the tag text. Keep (0,0,0) for automatic center position"))
        obj.addProperty("App::PropertyAngle","TagRotation","Arch",QT_TRANSLATE_NOOP("App::Property","The rotation of the tag text"))
        obj.addProperty("App::PropertyFile","FontFile","Arch",QT_TRANSLATE_NOOP("App::Property","The font of the tag text"))
        obj.addProperty("App::PropertyBool","MakeFace","Arch",QT_TRANSLATE_NOOP("App::Property","If True, the object is rendered as a face, if possible."))
        obj.Proxy = self
        self.Type = "PanelCut"
        obj.TagText = "%tag%"
        obj.MakeFace = False
        obj.TagSize = 10
        obj.FontFile = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Draft").GetString("FontFile","")

    def execute(self, obj):
        pl = obj.Placement
        if obj.Source:
            base = None
            n = None
            if Draft.getType(obj.Source) == "Panel":
                import Part,DraftGeomUtils
                baseobj = None
                if obj.Source.CloneOf:
                    baseobj = obj.Source.CloneOf.Base
                if obj.Source.Base:
                    baseobj = obj.Source.Base
                if baseobj:
                    if baseobj.isDerivedFrom("Part::Feature"):
                        if baseobj.Shape.Solids:
                            center = baseobj.Shape.BoundBox.Center
                            diag = baseobj.Shape.BoundBox.DiagonalLength
                            if obj.Source.Normal.Length:
                                n = obj.Source.Normal
                            elif baseobj.isDerivedFrom("Part::Extrusion"):
                                n = baseobj.Dir
                            if not n:
                                n = Vector(0,0,1)
                            plane = Part.makePlane(diag,diag,center,n)
                            plane.translate(center.sub(plane.BoundBox.Center))
                            wires = []
                            for sol in baseobj.Shape.Solids:
                                s = sol.section(plane)
                                wires.extend(DraftGeomUtils.findWires(s.Edges))
                            if wires:
                                base = self.buildCut(obj,wires)
                        else:
                            base = self.buildCut(obj,baseobj.Shape.Wires)
                            for w in base.Wires:
                                n = DraftGeomUtils.getNormal(w)
                                if n:
                                    break
                            if not n:
                                n = Vector(0,0,1)
                        if base and n:
                            base.translate(base.BoundBox.Center.negative())
                            r = FreeCAD.Rotation(n,Vector(0,0,1))
                            base.rotate(Vector(0,0,0),r.Axis,math.degrees(r.Angle))
                    elif baseobj.isDerivedFrom("Mesh::Feature"):
                        return
                else:
                    l2 = obj.Source.Length/2
                    w2 = obj.Source.Width/2
                    v1 = Vector(-l2,-w2,0)
                    v2 = Vector(l2,-w2,0)
                    v3 = Vector(l2,w2,0)
                    v4 = Vector(-l2,w2,0)
                    base = Part.makePolygon([v1,v2,v3,v4,v1])
                if base:
                    self.outline = base
                    if obj.FontFile and obj.TagText and obj.TagSize.Value:
                        if obj.TagPosition.Length == 0:
                            pos = base.BoundBox.Center
                        else:
                            pos = obj.TagPosition
                        if obj.TagText == "%tag%":
                            string = obj.Source.Tag
                        elif obj.TagText == "%label%":
                            string = obj.Source.Label
                        elif obj.TagText == "%description%":
                            string = obj.Source.Description
                        else:
                            string = obj.TagText
                        chars = []
                        for char in Part.makeWireString(string,obj.FontFile,obj.TagSize.Value,0):
                            chars.extend(char)
                        textshape = Part.Compound(chars)
                        textshape.translate(pos.sub(textshape.BoundBox.Center))
                        textshape.rotate(textshape.BoundBox.Center,Vector(0,0,1),obj.TagRotation.Value)
                        self.tag = textshape
                        base = Part.Compound([base,textshape])
                    else:
                        base = Part.Compound([base])
                    obj.Shape = base
                    obj.Placement = pl

    def buildCut(self,obj,wires):

        """buildCut(obj,wires): builds the object shape"""
        import Part
        if hasattr(obj,"MakeFace"):
            if obj.MakeFace:
                face = None
                if len(wires) > 1:
                    d = 0
                    ow = None
                    for w in wires:
                        if w.BoundBox.DiagonalLength > d:
                            d = w.BoundBox.DiagonalLength
                            ow = w
                    if ow:
                        face = Part.Face(ow)
                        for w in wires:
                            if w.hashCode() != ow.hashCode():
                                wface = Part.Face(w)
                                face = face.cut(wface)
                else:
                    face = Part.Face(wires[0])
                if face:
                    return face
        return Part.makeCompound(wires)

    def getWires(self, obj):

        """getWires(obj): returns a tuple containing 3 shapes
        that define the panel outline, the panel holes, and
        tags (engravings): (outline,holes,tags). Any of these can
        be None if nonexistent"""
        tag = None
        outl = None
        inl = None
        if not hasattr(self,"outline"):
            self.execute(obj)
        if not hasattr(self,"outline"):
            return None
        outl = self.outline.copy()
        if hasattr(self,"tag"):
            tag = self.tag.copy()
        if tag:
            tag.Placement = obj.Placement.multiply(tag.Placement)

        outl = self.outline.copy()
        outl.Placement = obj.Placement.multiply(outl.Placement)
        if len(outl.Wires) > 1:
            # separate outline
            d = 0
            ow = None
            for w in outl.Wires:
                if w.BoundBox.DiagonalLength > d:
                    d = w.BoundBox.DiagonalLength
                    ow = w
            if ow:
                inl = Part.Compound([w for w in outl.Wires if w.hashCode() != ow.hashCode()])
                outl = Part.Compound([ow])
        else:
            inl = None
            outl = Part.Compound([outl.Wires[0]])
        return (outl, inl, tag)

class ViewProviderPanelCut(Draft._ViewProviderDraft):
    "a view provider for the panel cut object"

    def __init__(self,vobj):
        Draft._ViewProviderDraft.__init__(self,vobj)
        vobj.addProperty("App::PropertyLength","Margin","Arch",QT_TRANSLATE_NOOP("App::Property","A margin inside the boundary"))
        vobj.addProperty("App::PropertyBool","ShowMargin","Arch",QT_TRANSLATE_NOOP("App::Property","Turns the display of the margin on/off"))

    def attach(self,vobj):
        Draft._ViewProviderDraft.attach(self,vobj)
        from pivy import coin
        self.coords = coin.SoCoordinate3()
        self.lineset = coin.SoLineSet()
        self.lineset.numVertices.setValue(-1)
        lineStyle = coin.SoDrawStyle()
        lineStyle.linePattern = 0x0f0f
        self.color = coin.SoBaseColor()
        self.switch = coin.SoSwitch()
        sep = coin.SoSeparator()
        self.switch.whichChild = -1
        sep.addChild(self.color)
        sep.addChild(lineStyle)
        sep.addChild(self.coords)
        sep.addChild(self.lineset)
        self.switch.addChild(sep)
        vobj.Annotation.addChild(self.switch)
        self.onChanged(vobj,"ShowMargin")
        self.onChanged(vobj,"LineColor")

    def onChanged(self,vobj,prop):
        if prop in ["Margin","ShowMargin"]:
            if hasattr(vobj,"Margin") and hasattr(vobj,"ShowMargin"):
                if (vobj.Margin.Value > 0) and vobj.Object.Shape and vobj.ShowMargin:
                    self.lineset.numVertices.setValue(-1)
                    if vobj.Object.Shape.Wires:
                        d = 0
                        dw = None
                        for w in vobj.Object.Shape.Wires:
                            if w.BoundBox.DiagonalLength > d:
                                d = w.BoundBox.DiagonalLength
                                dw = w
                        if dw:
                            ow = dw.makeOffset2D(vobj.Margin.Value)
                            verts = []
                            for v in ow.OrderedVertexes:
                                v = vobj.Object.Placement.inverse().multVec(v.Point)
                                verts.append((v.x,v.y,v.z))
                            if dw.isClosed():
                                verts.append(verts[0])
                        self.coords.point.setValues(verts)
                        self.lineset.numVertices.setValue(len(verts))
                        self.switch.whichChild = 0
                else:
                    self.switch.whichChild = -1
        elif prop == "LineColor":
            if hasattr(vobj,"LineColor"):
                c = vobj.LineColor
                self.color.rgb.setValue(c[0],c[1],c[2])
        Draft._ViewProviderDraft.onChanged(self,vobj,prop)

    def updateData(self,obj,prop):
        if prop in ["Shape"]:
            self.onChanged(obj.ViewObject,"Margin")
        Draft._ViewProviderDraft.updateData(self,obj,prop)


class PanelSheet(Draft._DraftObject):
    "A collection of Panel cuts under a sheet"

    def __init__(self, obj):
        Draft._DraftObject.__init__(self,obj)
        obj.addProperty("App::PropertyLinkList","Group","Arch",QT_TRANSLATE_NOOP("App::Property","The linked Panel cuts"))
        obj.addProperty("App::PropertyString","TagText","Arch",QT_TRANSLATE_NOOP("App::Property","The tag text to display"))
        obj.addProperty("App::PropertyLength","TagSize","Arch",QT_TRANSLATE_NOOP("App::Property","The size of the tag text"))
        obj.addProperty("App::PropertyVector","TagPosition","Arch",QT_TRANSLATE_NOOP("App::Property","The position of the tag text. Keep (0,0,0) for automatic center position"))
        obj.addProperty("App::PropertyAngle","TagRotation","Arch",QT_TRANSLATE_NOOP("App::Property","The rotation of the tag text"))
        obj.addProperty("App::PropertyFile","FontFile","Arch",QT_TRANSLATE_NOOP("App::Property","The font of the tag text"))
        obj.addProperty("App::PropertyLength","Width","Arch",QT_TRANSLATE_NOOP("App::Property","The width of the sheet"))
        obj.addProperty("App::PropertyLength","Height","Arch",QT_TRANSLATE_NOOP("App::Property","The height of the sheet"))
        obj.addProperty("App::PropertyPercent","FillRatio","Arch",QT_TRANSLATE_NOOP("App::Property","The fill ratio of this sheet"))
        obj.addProperty("App::PropertyBool","MakeFace","Arch",QT_TRANSLATE_NOOP("App::Property","If True, the object is rendered as a face, if possible."))
        obj.addProperty("App::PropertyAngle","GrainDirection","Arch",QT_TRANSLATE_NOOP("App::Property","Specifies an angle for the wood grain (Clockwise, 0 is North)"))
        obj.Proxy = self
        self.Type = "PanelSheet"
        obj.TagSize = 10
        p = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Arch")
        obj.Width = p.GetFloat("PanelLength",1000)
        obj.Height = p.GetFloat("PanelWidth",1000)
        obj.MakeFace = False
        obj.FontFile = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Draft").GetString("FontFile","")
        obj.setEditorMode("FillRatio",2)

    def execute(self, obj):
        import Part
        self.sheettag = None
        self.sheetborder = None
        pl = obj.Placement
        if obj.Width.Value and obj.Height.Value:
            l2 = obj.Width.Value/2
            w2 = obj.Height.Value/2
            v1 = Vector(-l2,-w2,0)
            v2 = Vector(l2,-w2,0)
            v3 = Vector(l2,w2,0)
            v4 = Vector(-l2,w2,0)
            base = Part.makePolygon([v1,v2,v3,v4,v1])
            if hasattr(obj,"MakeFace"):
                if obj.MakeFace:
                    base = Part.Face(base)
            self.sheetborder = base
            wires = []
            area = obj.Width.Value * obj.Height.Value
            subarea = 0
            for v in obj.Group:
                if v.isDerivedFrom("Part::Feature"):
                    wires.extend(v.Shape.Wires)
                    if Draft.getType(v) == "PanelCut":
                        if v.Source:
                            subarea += v.Source.Area.Value
                    else:
                        for w in v.Shape.Wires:
                            if w.isClosed():
                                f = Part.Face(w)
                                subarea += f.Area
            if wires:
                base = Part.Compound([base]+wires)
            if obj.FontFile and obj.TagText and obj.TagSize.Value:
                chars = []
                for char in Part.makeWireString(obj.TagText,obj.FontFile,obj.TagSize.Value,0):
                    chars.extend(char)
                textshape = Part.Compound(chars)
                textshape.translate(obj.TagPosition)
                textshape.rotate(textshape.BoundBox.Center,Vector(0,0,1),obj.TagRotation.Value)
                self.sheettag = textshape
                base = Part.Compound([base,textshape])
            obj.Shape = base
            obj.Placement = pl
            obj.FillRatio = int((subarea/area)*100)

    def getOutlines(self,obj,transform=False):
        """getOutlines(obj,transform=False): returns a list of compounds whose wires define the
        outlines of the panels in this sheet. If transform is True, the placement of
        the sheet will be added to each wire"""

        outp = []
        for p in obj.Group:
            ispanel = False
            if hasattr(p,"Proxy"):
                if hasattr(p.Proxy,"getWires"):
                    ispanel = True
                    w = p.Proxy.getWires(p)
                    if w[0]:
                        w = w[0]
                        if transform:
                            w.Placement = obj.Placement.multiply(w.Placement)
                        outp.append(w)
            if not ispanel:
                if p.isDerivedFrom("Part::Feature"):
                    for w in p.Shape.Wires:
                        if transform:
                            w.Placement = obj.Placement.multiply(w.Placement)
                        outp.append(w)
        return outp

    def getHoles(self,obj,transform=False):
        """getHoles(obj,transform=False): returns a list of compound whose wires define the
        holes contained in the panels in this sheet. If transform is True, the placement of
        the sheet will be added to each wire"""

        outp = []
        for p in obj.Group:
            if hasattr(p,"Proxy"):
                if hasattr(p.Proxy,"getWires"):
                    w = p.Proxy.getWires(p)
                    if w[1]:
                        w = w[1]
                        if transform:
                            w.Placement = obj.Placement.multiply(w.Placement)
                        outp.append(w)
        return outp

    def getTags(self,obj,transform=False):
        """getTags(obj,transform=False): returns a list of compounds whose wires define the
        tags (engravings) contained in the panels in this sheet and the sheet intself.
        If transform is True, the placement of the sheet will be added to each wire.
        Warning, the wires returned by this function may not be closed,
        depending on the font"""

        outp = []
        for p in obj.Group:
            if hasattr(p,"Proxy"):
                if hasattr(p.Proxy,"getWires"):
                    w = p.Proxy.getWires(p)
                    if w[2]:
                        w = w[2]
                        if transform:
                            w.Placement = obj.Placement.multiply(w.Placement)
                        outp.append(w)
        if self.sheettag is not None:
            w = self.sheettag.copy()
            if transform:
                w.Placement = obj.Placement.multiply(w.Placement)
            outp.append(w)

        return outp


class ViewProviderPanelSheet(Draft._ViewProviderDraft):
    "a view provider for the panel sheet object"

    def __init__(self,vobj):
        Draft._ViewProviderDraft.__init__(self,vobj)
        vobj.addProperty("App::PropertyLength","Margin","Arch",QT_TRANSLATE_NOOP("App::Property","A margin inside the boundary"))
        vobj.addProperty("App::PropertyBool","ShowMargin","Arch",QT_TRANSLATE_NOOP("App::Property","Turns the display of the margin on/off"))
        vobj.addProperty("App::PropertyBool","ShowGrain","Arch",QT_TRANSLATE_NOOP("App::Property","Turns the display of the wood grain texture on/off"))
        vobj.PatternSize = 0.0035

    def getIcon(self):
        return ":/icons/Draft_Drawing.svg"

    def setEdit(self,vobj,mode):
        if mode == 0:
            taskd = SheetTaskPanel(vobj.Object)
            taskd.update()
            FreeCADGui.Control.showDialog(taskd)
            return True
        return False

    def unsetEdit(self,vobj,mode):
        FreeCADGui.Control.closeDialog()
        return False

    def attach(self,vobj):
        Draft._ViewProviderDraft.attach(self,vobj)
        from pivy import coin
        self.coords = coin.SoCoordinate3()
        self.lineset = coin.SoLineSet()
        self.lineset.numVertices.setValue(-1)
        lineStyle = coin.SoDrawStyle()
        lineStyle.linePattern = 0x0f0f
        self.color = coin.SoBaseColor()
        self.switch = coin.SoSwitch()
        sep = coin.SoSeparator()
        self.switch.whichChild = -1
        sep.addChild(self.color)
        sep.addChild(lineStyle)
        sep.addChild(self.coords)
        sep.addChild(self.lineset)
        self.switch.addChild(sep)
        vobj.Annotation.addChild(self.switch)
        self.onChanged(vobj,"ShowMargin")
        self.onChanged(vobj,"LineColor")

    def onChanged(self,vobj,prop):
        if prop in ["Margin","ShowMargin"]:
            if hasattr(vobj,"Margin") and hasattr(vobj,"ShowMargin"):
                if (vobj.Margin.Value > 0) and (vobj.Margin.Value < vobj.Object.Width.Value/2) and (vobj.Margin.Value < vobj.Object.Height.Value/2):
                    l2 = vobj.Object.Width.Value/2
                    w2 = vobj.Object.Height.Value/2
                    v = vobj.Margin.Value
                    v1 = (-l2+v,-w2+v,0)
                    v2 = (l2-v,-w2+v,0)
                    v3 = (l2-v,w2-v,0)
                    v4 = (-l2+v,w2-v,0)
                    self.coords.point.setValues([v1,v2,v3,v4,v1])
                    self.lineset.numVertices.setValue(5)
                if vobj.ShowMargin:
                    self.switch.whichChild = 0
                else:
                    self.switch.whichChild = -1
        elif prop == "LineColor":
            if hasattr(vobj,"LineColor"):
                c = vobj.LineColor
                self.color.rgb.setValue(c[0],c[1],c[2])
        elif prop == "ShowGrain":
            if hasattr(vobj,"ShowGrain"):
                if vobj.ShowGrain:
                    vobj.Pattern = "woodgrain"
                else:
                    vobj.Pattern = "None"
        Draft._ViewProviderDraft.onChanged(self,vobj,prop)
    

    def updateData(self,obj,prop):
        if prop in ["Width","Height"]:
            self.onChanged(obj.ViewObject,"Margin")
        elif prop == "GrainDirection":
            if hasattr(self,"texcoords"):
                if self.texcoords:
                    s = FreeCAD.Vector(self.texcoords.directionS.getValue().getValue()).Length
                    vS  = DraftVecUtils.rotate(FreeCAD.Vector(s,0,0),-math.radians(obj.GrainDirection.Value))
                    vT  = DraftVecUtils.rotate(FreeCAD.Vector(0,s,0),-math.radians(obj.GrainDirection.Value))
                    self.texcoords.directionS.setValue(vS.x,vS.y,vS.z)
                    self.texcoords.directionT.setValue(vT.x,vT.y,vT.z)
        Draft._ViewProviderDraft.updateData(self,obj,prop)


class SheetTaskPanel(ArchComponent.ComponentTaskPanel):

    def __init__(self,obj):
        ArchComponent.ComponentTaskPanel.__init__(self)
        self.obj = obj
        self.optwid = QtGui.QWidget()
        self.optwid.setWindowTitle(QtGui.QApplication.translate("Arch", "Tools", None))
        lay = QtGui.QVBoxLayout(self.optwid)
        self.editButton = QtGui.QPushButton(self.optwid)
        self.editButton.setIcon(QtGui.QIcon(":/icons/Draft_Edit.svg"))
        self.editButton.setText(QtGui.QApplication.translate("Arch", "Edit views positions", None))
        lay.addWidget(self.editButton)
        QtCore.QObject.connect(self.editButton, QtCore.SIGNAL("clicked()"), self.editNodes)
        self.form = [self.form,self.optwid]

    def editNodes(self):
        FreeCADGui.Control.closeDialog()
        FreeCADGui.runCommand("Draft_Edit")


if FreeCAD.GuiUp:

    class CommandPanelGroup:

        def GetCommands(self):
            return tuple(['Arch_Panel','Arch_Panel_Cut','Arch_Panel_Sheet'])
        def GetResources(self):
            return { 'MenuText': QT_TRANSLATE_NOOP("Arch_PanelTools",'Panel tools'),
                     'ToolTip': QT_TRANSLATE_NOOP("Arch_PanelTools",'Panel tools')
                   }
        def IsActive(self):
            return not FreeCAD.ActiveDocument is None

    FreeCADGui.addCommand('Arch_Panel',CommandPanel())
    FreeCADGui.addCommand('Arch_Panel_Cut',CommandPanelCut())
    FreeCADGui.addCommand('Arch_Panel_Sheet',CommandPanelSheet())
    FreeCADGui.addCommand('Arch_PanelTools', CommandPanelGroup())
