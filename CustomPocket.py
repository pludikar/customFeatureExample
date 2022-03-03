#Author-Autodesk
#Description-Demonstrates the creation of a custom feature.

from pickletools import ArgumentDescriptor
from tkinter import E
from tkinter.messagebox import NO
from venv import create
import adsk.core, adsk.fusion, traceback
import logging
import os
from .decorators import eventHandler, HandlerCollection

appPath = os.path.dirname(os.path.abspath(__file__))

logger = logging.getLogger('CustomCove')

if len(logger.handlers):
    del logger.handlers[:]

logger.setLevel(logging.WARNING)
formatter = logging.Formatter('%(asctime)s; %(name)s; %(levelname)s; %(lineno)d; %(funcName)s ; %(message)s')
logHandler = logging.FileHandler(os.path.join(appPath, 'customCove.log'), mode='w')
logHandler.setFormatter(formatter)
logHandler.setLevel(logging.DEBUG)
logger.addHandler(logHandler)
logger.setLevel(logging.WARNING)

_app: adsk.core.Application = None
_ui: adsk.core.UserInterface = None

# des: adsk.fusion.Design = None
root = None

_customFeatureDef: adsk.fusion.CustomFeature = None

_edgeSelectInput: adsk.core.SelectionCommandInput = None
_radiusInput: adsk.core.ValueCommandInput = None

_alreadyCreatedCustomFeature: adsk.fusion.CustomFeature = None
_restoreTimelineObject: adsk.fusion.TimelineObject = None
_alreadyCreated: bool = False
_isRolledForEdit = False
_computeCustomFeatureEventHandle = None

class NotInRolledBackState(Exception):
    pass

def run(context):
    try:
        global _app, _ui 
        global root, _computeCustomFeatureEventHandle
        _app = adsk.core.Application.get()
        _ui  = _app.userInterface
        des: adsk.fusion.Design = _app.activeProduct
        root = des.rootComponent
        
        handlerGroup = 'run'
        logger.debug("Running")
        # Create the command definition for the creation command.
        createCmdDef = _ui.commandDefinitions.addButtonDefinition('adskCustomCoveCreate', 
                                                                    'Custom Cove', 
                                                                    'Adds a pocket at a point.', 
                                                                    'Resources/CustomCove')    

        # Add the create button after the Emboss command in the CREATE panel of the SOLID tab.
        solidWS = _ui.workspaces.itemById('FusionSolidEnvironment')
        panel = solidWS.toolbarPanels.itemById('SolidCreatePanel')
        btncontrol = panel.controls.addCommand(createCmdDef, 'EmbossCmd', False).isPromoted = True
        # btncontrol.isPromoted = True      

        # Create the command definition for the edit command.
        editCmdDef = _ui.commandDefinitions.addButtonDefinition('adskCustomCoveEdit', 
                                                                'Edit Custom Cove', 
                                                                'Edit custom pocket.', '')        

        # Connect to the command created event for the create command.
        HandlerCollection.remove(groupId =  handlerGroup)
        CreateCoveCommandCreatedHandler(event = createCmdDef.commandCreated, groupId =  handlerGroup)

        # Connect to the command created event for the edit command.
        EditCoveCommandCreatedHandler(event = editCmdDef.commandCreated, groupId =  handlerGroup)

        # Create the custom feature definition.
        global _customFeatureDef
        _customFeatureDef = adsk.fusion.CustomFeatureDefinition.create('adskCustomCove', 
                                                                        'Custom Cove', 
                                                                        'Resources/CustomCove')
        _customFeatureDef.editCommandId = 'adskCustomCoveEdit'

        # Connect to the compute event for the custom feature.
        _computeCustomFeatureEventHandle = ComputeCustomFeature(event = _customFeatureDef.customFeatureCompute, groupId =  handlerGroup)
    except:
        logger.exception('Exception')
        showMessage('Run Failed:\n{}'.format(traceback.format_exc()))


def stop(context):
    logger.debug('Stopping')
    for handler in logger.handlers:
        handler.flush()
        handler.close()
        logger.removeHandler(handler)
    try:
        # Remove all UI elements.
        logger.debug('Stopping')
        solidWS = _ui.workspaces.itemById('FusionSolidEnvironment')
        panel = solidWS.toolbarPanels.itemById('SolidCreatePanel')
        cntrl = panel.controls.itemById('adskCustomCoveCreate')
        if cntrl:
            cntrl.deleteMe()
            
        cmdDef = _ui.commandDefinitions.itemById('adskCustomCoveCreate')
        if cmdDef:
            cmdDef.deleteMe()

        cmdDef = _ui.commandDefinitions.itemById('adskCustomCoveEdit')
        if cmdDef:
            cmdDef.deleteMe()

        HandlerCollection.remove()
    except:
        logger.exception('Exception')
        showMessage('Stop Failed:\n{}'.format(traceback.format_exc()))


# Define the command inputs needed to get the input from the user for the
# creation of the feauture and connect to the command related events.
@eventHandler(handler_cls = adsk.core.CommandCreatedEventHandler)
def CreateCoveCommandCreatedHandler(eventArgs: adsk.core.CommandCreatedEventArgs):
    try:
        global _edgeSelectInput, _radiusInput

        logger.debug('Creating Cove Command')
        handlerGroup = 'CreateCoveCommandCreatedHandler'
        cmd = eventArgs.command
        inputs = cmd.commandInputs
        des: adsk.fusion.Design = _app.activeProduct

        # Create the selection input to select the body(s).
        _edgeSelectInput = inputs.addSelectionInput('selectPoint', 
                                                        'Points', 
                                                        'Select point to define pocket position.')
        _edgeSelectInput.addSelectionFilter('Edges')
        _edgeSelectInput.tooltip = 'Select edge to define the bevel.'
        _edgeSelectInput.setSelectionLimits(1, 1)

        lengthUnits = des.unitsManager.defaultLengthUnits

        # Create the value input to get the fillet radius.
        radius = adsk.core.ValueInput.createByReal(0.5)
        _radiusInput = inputs.addValueInput('cornerRadius', 'Corner Radius', lengthUnits, radius)
                                            
        # Connect to the needed command related events.
        HandlerCollection.remove(handlerGroup)
        ExecutePreviewHandler(event = cmd.executePreview, groupId =  handlerGroup)

        CreateExecuteHandler(event = cmd.execute, groupId =  handlerGroup)

        PreSelectHandler(event = cmd.preSelect, groupId =  handlerGroup)

        ChangeHandler(event = cmd.inputChanged, groupId = handlerGroup) 

        ValidateInputsHandler(event = cmd.validateInputs, groupId =  handlerGroup)
    except:
        logger.exception('Exception')
        showMessage('CommandCreated failed: {}\n'.format(traceback.format_exc()))

@eventHandler(handler_cls = adsk.core.InputChangedEventHandler)
def ChangeHandler(eventArgs: adsk.core.InputChangedEventArgs):
    logger.debug('ChangeHandler')
    pass

# Event handler for the validateInputs event.
@eventHandler(handler_cls = adsk.core.ValidateInputsEventHandler)
def ValidateInputsHandler(eventArgs: adsk.core.ValidateInputsEventArgs):
    logger.debug('ValidateInputsHandler')
    try:
        # Verify the inputs have valid expressions.
        if not all( [_radiusInput.isValidExpression] ):
            eventArgs.areInputsValid = False
            return

        # Verify the sizes are valid.
        # diam = _radiusInput.value * 2
        # if diam + 0.01 > _lengthInput.value or diam + 0.01 > _widthInput.value:
        #     eventArgs.areInputsValid = False
        #     return
    except:
        logger.exception('Exception')
        showMessage('ValidateInputsHandler: {}\n'.format(traceback.format_exc()))

        
# Event handler for the execute event of the create command.
@eventHandler(handler_cls = adsk.core.CommandEventHandler)
def CreateExecuteHandler(eventArgs: adsk.core.CommandEventArgs):
    global _alreadyCreated, _computeCustomFeatureEventHandle
    logger.debug('CreateExecuteHandler')
    _computeCustomFeatureEventHandle.disable()
    try:
        # Create the body of the pocket.
        edge: adsk.fusion.BRepCoEdge = _edgeSelectInput.selection(0).entity

        des: adsk.fusion.Design = _app.activeProduct
        defLengthUnits = des.unitsManager.defaultLengthUnits

        covebody = CreateCove(edge, _radiusInput.value)

        comp = edge.body.parentComponent

        custFeatInput = comp.features.customFeatures.createInput(_customFeatureDef)

        radiusInput = adsk.core.ValueInput.createByString(_radiusInput.expression)             
        custFeatInput.addCustomParameter('radius', 'Radius', radiusInput,
                                            defLengthUnits, True)               


        # Subtract the pocket from the parametric body.
        paramBody = edge.body
        comp = paramBody.parentComponent
        baseFeat = comp.features.baseFeatures.add()
        baseFeat.startEdit()
        comp.bRepBodies.add(covebody, baseFeat)
        baseFeat.finishEdit()

        # Create a combine feature to subtract the pocket body from the part.
        combineFeature = None
        toolBodies = adsk.core.ObjectCollection.create()
        toolBodies.add(baseFeat.bodies.item(0))
        combineInput = comp.features.combineFeatures.createInput(paramBody, toolBodies)
        combineInput.isKeepToolBodies = False
        combineInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
        combineFeature = comp.features.combineFeatures.add(combineInput)
        
        # Create the custom feature input.
        # des: adsk.fusion.Design = _app.activeProduct
        # defLengthUnits = des.unitsManager.defaultLengthUnits
        custFeatInput.setStartAndEndFeatures(baseFeat, combineFeature)
        logger.debug(f'Execute - _alreadyCreated: {_alreadyCreated}')
        custFeat: adsk.fusion.CustomFeature = comp.features.customFeatures.add(custFeatInput)

        
        timeline = des.timeline
        markerPosition = timeline.markerPosition
        timelineObject = timeline.item(markerPosition - 1)
        # Roll the timeline to just before the custom feature being edited.
        timelineObject.rollTo(rollBefore = True)

        custFeat.dependencies.add('edge', edge) #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

        # Roll the timeline to its previous position.
        timelineObject.rollTo(False)
        _computeCustomFeatureEventHandle.enable()

    except:
        logger.exception('Exception')
        eventArgs.executeFailed = True
        showMessage('Execute: {}\n'.format(traceback.format_exc()))


@eventHandler(handler_cls = adsk.core.CommandCreatedEventHandler)
def EditCoveCommandCreatedHandler(eventArgs: adsk.core.CommandCreatedEventArgs):
    global _alreadyCreated, _computeCustomFeatureEventHandle
    global _alreadyCreatedCustomFeature
    global _edgeSelectInput, _radiusInput
    
    logger.debug('Edit Command created')
    try:
        _computeCustomFeatureEventHandle.disableOnce()
        handlerGroup = 'EditCoveCommandCreatedHandler'
        cmd = eventArgs.command
        inputs = cmd.commandInputs
        des: adsk.fusion.Design = _app.activeProduct
        defLengthUnits = des.unitsManager.defaultLengthUnits

        # Get the currently selected custom feature.
        _alreadyCreatedCustomFeature = _ui.activeSelections.item(0).entity
        if _alreadyCreatedCustomFeature is None:
            return

        # Create the selection input to select the sketch point.
        _edgeSelectInput = inputs.addSelectionInput('selectPoint', 
                                                        'edge', 
                                                        'Select point to define pocket position.')
        _edgeSelectInput.addSelectionFilter('SketchPoints')
        _edgeSelectInput.tooltip = 'Select point to define the center of the pocket.'
        _edgeSelectInput.setSelectionLimits(1, 1)

        # Get the collection of custom parameters for this custom feature.
        params = _alreadyCreatedCustomFeature.parameters

        # Create the value input to get the fillet radius.
        radius = adsk.core.ValueInput.createByString(params.itemById('radius').expression)
        _radiusInput = inputs.addValueInput('cornerRadius', 'Corner Radius', defLengthUnits, radius)
                                            
        # Connect to the needed command related events.
        HandlerCollection.remove(handlerGroup)
        ExecutePreviewHandler(event = cmd.executePreview, groupId =  handlerGroup)

        EditExecuteHandler(event = cmd.execute, groupId =  handlerGroup)

        PreSelectHandler(event = cmd.preSelect, groupId =  handlerGroup)

        EditActivateHandler(event = cmd.activate, groupId =  handlerGroup)

        ValidateInputsHandler(event = cmd.validateInputs, groupId =  handlerGroup)
    except:
        logger.exception('Exception')
        showMessage('CommandCreated failed: {}\n'.format(traceback.format_exc()))


# Event handler for the activate event.
@eventHandler(handler_cls = adsk.core.CommandEventHandler)
def EditActivateHandler(eventArgs: adsk.core.CommandEventArgs):
    global _restoreTimelineObject, _isRolledForEdit
    
    logger.debug('Edit Activate')
    try:
        des: adsk.fusion.Design = _app.activeProduct

        # Save the current position of the timeline.
        timeline = des.timeline
        markerPosition = timeline.markerPosition
        _restoreTimelineObject = timeline.item(markerPosition - 1)

        # Roll the timeline to just before the custom feature being edited.
        _alreadyCreatedCustomFeature.timelineObject.rollTo(rollBefore = True)

        _isRolledForEdit = True

        # Define a transaction marker so the the roll is not aborted with each change.
        eventArgs.command.beginStep()

        # Get the edge and add it to the selection input.
        edge = _alreadyCreatedCustomFeature.dependencies.itemById('edge').entity
        _edgeSelectInput.addSelection(edge)
    except:
        logger.exception('Exception')
        showMessage('Execute: {}\n'.format(traceback.format_exc()))


# Event handler for the execute event of the edit command.
@eventHandler(handler_cls = adsk.core.CommandEventHandler)
def EditExecuteHandler(eventArgs: adsk.core.CommandEventArgs):
    logger.debug('EditExecuteHandler')
    global _alreadyCreated
    global _alreadyCreatedCustomFeature
    global _isRolledForEdit

    try:

        edge = _edgeSelectInput.selection(0).entity

        # Update the parameters.
        params = _alreadyCreatedCustomFeature.parameters

        radiusParam = params.itemById('radius')
        radiusParam.expression = _radiusInput.expression

        # Update the feature.
        UpdateCove(_alreadyCreatedCustomFeature)

        # Update the point dependency.
        dependency = _alreadyCreatedCustomFeature.dependencies.itemById('edge')
        dependency.entity = edge

        # Roll the timeline to its previous position.
        if not _isRolledForEdit:
            raise NotInRolledBackState

        _restoreTimelineObject.rollTo(False)
        _isRolledForEdit = False

        _alreadyCreatedCustomFeature = None

        showMessage('Finished ExecuteHandler')
    except:
        logger.exception('Exception')
        showMessage('Execute: {}\n'.format(traceback.format_exc()))


# Event handler for the executePreview event.
@eventHandler(handler_cls = adsk.core.CommandEventHandler)
def ExecutePreviewHandler(eventArgs: adsk.core.CommandEventArgs):
    logger.debug('Execute Preview')
    try:
        # Get the settings from the inputs.
        edge: adsk.fusion.BrepEdge = _edgeSelectInput.selection(0).entity
        radius = _radiusInput.value

        # Create the fillet feature.
        covebody = CreateCove(edge, radius)

        # Create a base feature and add the body.
        paramBody = edge.body
        comp = paramBody.parentComponent

        baseFeat = comp.features.baseFeatures.add()
        baseFeat.startEdit()
        comp.bRepBodies.add(covebody, baseFeat)
        baseFeat.finishEdit()

        # Create a combine feature to subtract the pocket body from the part.
        toolBodies = adsk.core.ObjectCollection.create()
        toolBodies.add(baseFeat.bodies.item(0))
        combineInput = comp.features.combineFeatures.createInput(paramBody, toolBodies)
        combineInput.isKeepToolBodies = False
        combineInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
        comp.features.combineFeatures.add(combineInput)
    except:
        logger.exception('Exception')
        showMessage('ExecutePreview: {}\n'.format(traceback.format_exc()))       


# Controls what the user can select when the command is running.
# This checks to make sure the point is on a planar face and the
# body the point is on is not an external reference.
@eventHandler(handler_cls = adsk.core.SelectionEventHandler)
def PreSelectHandler(eventArgs: adsk.core.SelectionEventArgs):
    logger.debug('PreSelect')
    try:
        edge: adsk.fusion.BrepEdge = eventArgs.selection.entity

        if edge is None:
            eventArgs.isSelectable = False
            return

        # Verify the body is not from an XRef.
        if edge.assemblyContext:
            occ = edge.assemblyContext
            if occ.isReferencedComponent:
                eventArgs.isSelectable = False
                return
    except:
        logger.exception('Exception')
        showMessage('PreSelectEventHandler: {}\n'.format(traceback.format_exc()))


# Event handler to handle the compute of the custom feature.
@eventHandler(handler_cls = adsk.fusion.CustomFeatureEventHandler)
def ComputeCustomFeature(args: adsk.fusion.CustomFeatureEventArgs):
    logger.debug('ComputeCustomFeature')
    global _isRolledForEdit
    des: adsk.fusion.Design = _app.activeProduct

    try:
        if not _isRolledForEdit:
            computeRolled = True
            timeline = des.timeline
            markerPosition = timeline.markerPosition
            restoreTL = timeline.item(markerPosition - 1)
            # Roll the timeline to just before the custom feature being edited.
            restoreTL.rollTo(rollBefore = True)

        eventArgs: adsk.fusion.CustomFeatureEventArgs = args

        # Get the custom feature that is being computed.
        custFeature = eventArgs.customFeature

        # Get the original sketch point and the values from the custom feature.
        edge = custFeature.dependencies.itemById('edge').entity
        radius = custFeature.parameters.itemById('radius').value

        # Create a new temporary body for the pocket. 
        # This can return None when the point isn't on a face.
        covebody = CreateCove(edge, radius)
        if covebody is None:
            # Add a failure status message because it failed to create the pocket.
            eventArgs.computeStatus.statusMessages.addError('DRPOINT_COMPUTE_FAILED', '')
            return
        
        # Get the existing base feature and update the body.
        baseFeature: adsk.fusion.BaseFeature = None
        for feature in custFeature.features:
            if feature.objectType == adsk.fusion.BaseFeature.classType():
                baseFeature = feature
                break        

        # Update the body in the base feature.
        baseFeature.startEdit()
        body: adsk.fusion.BRepBody = baseFeature.bodies.item(0)
        baseFeature.updateBody(body, covebody)
        baseFeature.finishEdit()
        if computeRolled:
            computeRolled = False
            restoreTL.rollTo(False)
            
        adsk.doEvents()
    except:
        logger.exception('Exception')
        showMessage(f'CustomFeatureCompute: {traceback.format_exc()}\n')


# Utility function that given the position and pocket size builds
# a temporary B-Rep body is the tool body to create the pocket.
def CreateCove(edge: adsk.fusion.BRepEdge, radius):
    logger.debug('Creating covebody')
    try:
        if edge is None:
            return None

        # Define the pocket at the origin with the length in the X direction,
        # width in the Y direction, and depth in the -Z direction.
        tBRep: adsk.fusion.TemporaryBRepManager = adsk.fusion.TemporaryBRepManager.get()
        widthDir = adsk.core.Vector3D.create(0, 1, 0)
        startPoint:adsk.fusion.Point3D = None
        endPoint:adsk.fusion.Point3D = None
        face1 = edge.faces.item(0)
        _, startPoint, endPoint = edge.evaluator.getEndPoints()
        
        bodies = []
        bodies.append(tBRep.createCylinderOrCone(startPoint, radius,
                                                endPoint, radius ))                                                

        # Combine the bodies into a single body.
        newBody: adsk.fusion.BRepBody = None
        for body in bodies:
            if newBody is None:
                newBody = body
            else:
                tBRep.booleanOperation(newBody, body, adsk.fusion.BooleanTypes.UnionBooleanType)

        return newBody
    except:
        logger.exception('Exception')
        showMessage('CreateCove: {}\n'.format(traceback.format_exc()))


# Updates an existing custom pocket feature.
def UpdateCove(customFeature: adsk.fusion.CustomFeature) -> bool:
    logger.debug('UpdateCove')
    try:
        # Get the original sketch point and the values from the custom feature.
        edge: adsk.fusion.BrepEdge = customFeature.dependencies.itemById('edge').entity

        radius = customFeature.parameters.itemById('radius').value

        # Create a new temporary body for the pocket. This can return None when the point isn't on a face.
        covebody = CreateCove(edge, radius)
        if covebody is None:
            return False
        
        # Get the existing base feature and update the body.
        baseFeature: adsk.fusion.BaseFeature = None
        for feature in customFeature.features:
            if feature.objectType == adsk.fusion.BaseFeature.classType():
                baseFeature = feature
                break        

        # Update the body in the base feature.
        baseFeature.startEdit()
        body: adsk.fusion.BRepBody = baseFeature.bodies.item(0)
        baseFeature.updateBody(body, covebody)
        baseFeature.finishEdit()
        return True
    except:
        logger.exception('Exception')
        showMessage('UpdateFillet: {}\n'.format(traceback.format_exc()))
        return False


# Get the face the selected point lies on. This assumes the point is
# in root component space. The returned face will be in the context
# of the root component.
#
# There is a case where more than one face can be found but in this case
# None is returned. The case is when the point is very near the edge of
# the face so it is ambiguous which face the point is on.
def GetFaceUnderPoint(point: adsk.core.Point3D) -> adsk.fusion.BRepFace:
    global root
    des: adsk.fusion.Design = _app.activeProduct
    root = des.rootComponent

    foundFaces: adsk.core.ObjectCollection = root.findBRepUsingPoint(point, adsk.fusion.BRepEntityTypes.BRepFaceEntityType, 0.01, True)
    if foundFaces.count == 0:
        return None
    face: adsk.fusion.BRepFace = foundFaces.item(0)
    return face

def showMessage(message, error = False):
    textPalette: adsk.core.TextCommandPalette = _ui.palettes.itemById('TextCommands')
    textPalette.writeText(message)

    if error:
        _ui.messageBox(message)