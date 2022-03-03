#Author-Autodesk
#Description-Demonstrates the creation of a custom feature.

from venv import create
import adsk.core, adsk.fusion, traceback
import logging
import os

appPath = os.path.dirname(os.path.abspath(__file__))



logger = logging.getLogger('CustomPocket')

for handler in logger.handlers:
    handler.flush()
    handler.close()
    logger.removeHandler(handler)

logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s; %(name)s; %(levelname)s; %(lineno)d; %(funcName)s ; %(message)s')
logHandler = logging.FileHandler(os.path.join(appPath, 'customPocket.log'), mode='w')
logHandler.setFormatter(formatter)
logHandler.setLevel(logging.DEBUG)
logger.addHandler(logHandler)
logger.setLevel(logging.DEBUG)



_app: adsk.core.Application = None
_ui: adsk.core.UserInterface = None
_handlers = []

_customFeatureDef: adsk.fusion.CustomFeature = None

_pointSelectInput: adsk.core.SelectionCommandInput = None
_lengthInput: adsk.core.ValueCommandInput = None
_widthInput: adsk.core.ValueCommandInput = None
_depthInput: adsk.core.ValueCommandInput = None
_radiusInput: adsk.core.ValueCommandInput = None

_editedCustomFeature: adsk.fusion.CustomFeature = None
_restoreTimelineObject: adsk.fusion.TimelineObject = None
_updated: bool = False
_isRolledForEdit = False


def run(context):
    try:
        global _app, _ui
        _app = adsk.core.Application.get()
        _ui  = _app.userInterface
        logger.debug("Running")

        # Create the command definition for the creation command.
        createCmdDef = _ui.commandDefinitions.addButtonDefinition('adskCustomPocketCreate', 
                                                                    'Custom Pocket', 
                                                                    'Adds a pocket at a point.', 
                                                                    'Resources/CustomPocket')    

        # Add the create button after the Emboss command in the CREATE panel of the SOLID tab.
        solidWS = _ui.workspaces.itemById('FusionSolidEnvironment')
        panel = solidWS.toolbarPanels.itemById('SolidCreatePanel')
        btncontrol = panel.controls.addCommand(createCmdDef, 'EmbossCmd', False).isPromoted = True
        # btncontrol.isPromoted = True      

        # Create the command definition for the edit command.
        editCmdDef = _ui.commandDefinitions.addButtonDefinition('adskCustomPocketEdit', 
                                                                'Edit Custom Pocket', 
                                                                'Edit custom pocket.', '')        

        # Connect to the command created event for the create command.
        createCommandCreated = CreatePocketCommandCreatedHandler()
        createCmdDef.commandCreated.add(createCommandCreated)
        _handlers.append(createCommandCreated)

        # Connect to the command created event for the edit command.
        editCommandCreated = EditPocketCommandCreatedHandler()
        editCmdDef.commandCreated.add(editCommandCreated)
        _handlers.append(editCommandCreated)

        # Create the custom feature definition.
        global _customFeatureDef
        _customFeatureDef = adsk.fusion.CustomFeatureDefinition.create('adskCustomPocket', 
                                                                        'Custom Pocket', 
                                                                        'Resources/CustomPocket')
        _customFeatureDef.editCommandId = 'adskCustomPocketEdit'

        # Connect to the compute event for the custom feature.
        computeCustomFeature = ComputeCustomFeature()
        _customFeatureDef.customFeatureCompute.add(computeCustomFeature)
        _handlers.append(computeCustomFeature)
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
        cntrl = panel.controls.itemById('adskCustomPocketCreate')
        if cntrl:
            cntrl.deleteMe()
            
        cmdDef = _ui.commandDefinitions.itemById('adskCustomPocketCreate')
        if cmdDef:
            cmdDef.deleteMe()

        cmdDef = _ui.commandDefinitions.itemById('adskCustomPocketEdit')
        if cmdDef:
            cmdDef.deleteMe()
    except:
        logger.exception('Exception')
        showMessage('Stop Failed:\n{}'.format(traceback.format_exc()))


# Define the command inputs needed to get the input from the user for the
# creation of the feauture and connect to the command related events.
class CreatePocketCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        try:
            logger.debug('Creating Pocket Command')
            eventArgs = adsk.core.CommandCreatedEventArgs.cast(args)
            cmd = eventArgs.command
            inputs = cmd.commandInputs
            des: adsk.fusion.Design = _app.activeProduct

            global _pointSelectInput, _lengthInput, _widthInput, _depthInput, _radiusInput

            # Create the selection input to select the body(s).
            _pointSelectInput = inputs.addSelectionInput('selectPoint', 
                                                         'Points', 
                                                         'Select point to define pocket position.')
            _pointSelectInput.addSelectionFilter('SketchPoints')
            _pointSelectInput.tooltip = 'Select point to define the center of the pocket.'
            _pointSelectInput.setSelectionLimits(1, 1)

            # Create the value input to get the length.
            length = adsk.core.ValueInput.createByReal(5)
            lengthUnits = des.unitsManager.defaultLengthUnits
            _lengthInput = inputs.addValueInput('length', 'Length', lengthUnits, length)

            # Create the value input to get the width.
            width = adsk.core.ValueInput.createByReal(3)
            _widthInput = inputs.addValueInput('width', 'Width', lengthUnits, width)

            # Create the value input to get the depth.
            depth = adsk.core.ValueInput.createByReal(1)
            _depthInput = inputs.addValueInput('depth', 'Depth', lengthUnits, depth)

            # Create the value input to get the fillet radius.
            radius = adsk.core.ValueInput.createByReal(0.5)
            _radiusInput = inputs.addValueInput('cornerRadius', 'Corner Radius', lengthUnits, radius)
                                                
            # Connect to the needed command related events.
            onExecutePreview = ExecutePreviewHandler()
            cmd.executePreview.add(onExecutePreview)
            _handlers.append(onExecutePreview)

            onExecute = CreateExecuteHandler()
            cmd.execute.add(onExecute)
            _handlers.append(onExecute)  

            onPreSelect = PreSelectHandler()
            cmd.preSelect.add(onPreSelect)
            _handlers.append(onPreSelect)

            onValidate = ValidateInputsHandler()
            cmd.validateInputs.add(onValidate)
            _handlers.append(onValidate)
        except:
            logger.exception('Exception')
            showMessage('CommandCreated failed: {}\n'.format(traceback.format_exc()))


# Event handler for the validateInputs event.
class ValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        logger.debug('ValidateInputsHandler')
        try:
            eventArgs = adsk.core.ValidateInputsEventArgs.cast(args)

            # Verify the inputs have valid expressions.
            if not all( [_lengthInput.isValidExpression, _widthInput.isValidExpression,
                        _depthInput.isValidExpression, _radiusInput.isValidExpression] ):
                eventArgs.areInputsValid = False
                return

            # Verify the sizes are valid.
            diam = _radiusInput.value * 2
            if diam + 0.01 > _lengthInput.value or diam + 0.01 > _widthInput.value:
                eventArgs.areInputsValid = False
                return
        except:
            logger.exception('Exception')
            showMessage('ValidateInputsHandler: {}\n'.format(traceback.format_exc()))

        
# Event handler for the execute event of the create command.
class CreateExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        logger.debug('CreateExecuteHandler')
        try:
            eventArgs = adsk.core.CommandEventArgs.cast(args)        

            # Create the body of the pocket.
            skPoint: adsk.fusion.SketchPoint = _pointSelectInput.selection(0).entity         
            pocketBody = CreatePocketBody(skPoint.worldGeometry, _lengthInput.value, 
                                          _widthInput.value, _depthInput.value, 
                                          _radiusInput.value)

            # Subtract the pocket from the parametric body.
            face = GetFaceUnderPoint(skPoint.worldGeometry)
            paramBody = face.body
            comp = paramBody.parentComponent
            baseFeat = comp.features.baseFeatures.add()
            baseFeat.startEdit()
            comp.bRepBodies.add(pocketBody, baseFeat)
            baseFeat.finishEdit()

            # Create a combine feature to subtract the pocket body from the part.
            combineFeature = None
            toolBodies = adsk.core.ObjectCollection.create()
            toolBodies.add(baseFeat.bodies.item(0))
            combineInput = comp.features.combineFeatures.createInput(paramBody, toolBodies)
            combineInput.isKeepToolBodies=False
            combineInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
            combineFeature = comp.features.combineFeatures.add(combineInput)
            
            # Create the custom feature input.
            des: adsk.fusion.Design = _app.activeProduct
            defLengthUnits = des.unitsManager.defaultLengthUnits
            custFeatInput = comp.features.customFeatures.createInput(_customFeatureDef)

            lengthInput = adsk.core.ValueInput.createByString(_lengthInput.expression)
            custFeatInput.addCustomParameter('length', 'Length', lengthInput,
                                              defLengthUnits, True)
            widthInput = adsk.core.ValueInput.createByString(_widthInput.expression)               
            custFeatInput.addCustomParameter('width', 'Width', widthInput,
                                              defLengthUnits, True)  
            depthInput = adsk.core.ValueInput.createByString(_depthInput.expression)             
            custFeatInput.addCustomParameter('depth', 'Depth', depthInput,
                                              defLengthUnits, True) 
            radiusInput = adsk.core.ValueInput.createByString(_radiusInput.expression)             
            custFeatInput.addCustomParameter('radius', 'Radius', radiusInput,
                                              defLengthUnits, True)               

            custFeatInput.addDependency('point', skPoint)

            custFeatInput.setStartAndEndFeatures(baseFeat, combineFeature)
            comp.features.customFeatures.add(custFeatInput)
        except:
            logger.exception('Exception')
            eventArgs.executeFailed = True
            showMessage('Execute: {}\n'.format(traceback.format_exc()))


class EditPocketCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        logger.debug('Edit Command created')
        try:
            eventArgs = adsk.core.CommandCreatedEventArgs.cast(args)
            cmd = eventArgs.command
            inputs = cmd.commandInputs
            des: adsk.fusion.Design = _app.activeProduct
            defLengthUnits = des.unitsManager.defaultLengthUnits

            # Get the currently selected custom feature.
            global _editedCustomFeature
            _editedCustomFeature = _ui.activeSelections.item(0).entity
            if _editedCustomFeature is None:
                return

            global _pointSelectInput, _lengthInput, _widthInput, _depthInput, _radiusInput

            # Create the selection input to select the sketch point.
            _pointSelectInput = inputs.addSelectionInput('selectPoint', 
                                                         'Point', 
                                                         'Select point to define pocket position.')
            _pointSelectInput.addSelectionFilter('SketchPoints')
            _pointSelectInput.tooltip = 'Select point to define the center of the pocket.'
            _pointSelectInput.setSelectionLimits(1, 1)

            # Get the collection of custom parameters for this custom feature.
            params = _editedCustomFeature.parameters

            # Create the value input to get the length.
            length = adsk.core.ValueInput.createByString(params.itemById('length').expression)
            _lengthInput = inputs.addValueInput('length', 'Length', defLengthUnits, length)

            # Create the value input to get the width.
            width = adsk.core.ValueInput.createByString(params.itemById('width').expression)
            _widthInput = inputs.addValueInput('width', 'Width', defLengthUnits, width)

            # Create the value input to get the depth.
            depth = adsk.core.ValueInput.createByString(params.itemById('depth').expression)
            _depthInput = inputs.addValueInput('depth', 'Depth', defLengthUnits, depth)

            # Create the value input to get the fillet radius.
            radius = adsk.core.ValueInput.createByString(params.itemById('radius').expression)
            _radiusInput = inputs.addValueInput('cornerRadius', 'Corner Radius', defLengthUnits, radius)
                                                
            # Connect to the needed command related events.
            onExecutePreview = ExecutePreviewHandler()
            cmd.executePreview.add(onExecutePreview)
            _handlers.append(onExecutePreview)

            onExecute = EditExecuteHandler()
            cmd.execute.add(onExecute)
            _handlers.append(onExecute)  

            onPreSelect = PreSelectHandler()
            cmd.preSelect.add(onPreSelect)
            _handlers.append(onPreSelect)

            onActivate = EditActivateHandler()
            cmd.activate.add(onActivate)
            _handlers.append(onActivate)

            onValidate = ValidateInputsHandler()
            cmd.validateInputs.add(onValidate)
            _handlers.append(onValidate)
        except:
            logger.exception('Exception')
            showMessage('CommandCreated failed: {}\n'.format(traceback.format_exc()))


# Event handler for the activate event.
class EditActivateHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        logger.debug('Edit Activate')
        try:
            eventArgs = adsk.core.CommandEventArgs.cast(args)
            des: adsk.fusion.Design = _app.activeProduct

            # Save the current position of the timeline.
            timeline = des.timeline
            markerPosition = timeline.markerPosition
            global _restoreTimelineObject, _isRolledForEdit
            _restoreTimelineObject = timeline.item(markerPosition - 1)

            # Roll the timeline to just before the custom feature being edited.
            _editedCustomFeature.timelineObject.rollTo(rollBefore = True)
            _isRolledForEdit = True

            # Define a transaction marker so the the roll is not aborted with each change.
            eventArgs.command.beginStep()

            # Get the point and add it to the selection input.
            skPoint = _editedCustomFeature.dependencies.itemById('point').entity
            _pointSelectInput.addSelection(skPoint)
        except:
            logger.exception('Exception')
            showMessage('Execute: {}\n'.format(traceback.format_exc()))


# Event handler for the execute event of the edit command.
class EditExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        logger.debug('EditExecuteHandler')
        try:
            global _editedCustomFeature
            eventArgs = adsk.core.CommandEventArgs.cast(args)        

            point = _pointSelectInput.selection(0).entity

            # Update the parameters.
            params = _editedCustomFeature.parameters
            lengthParam = params.itemById('length')
            lengthParam.expression = _lengthInput.expression
            widthParam = params.itemById('width')
            widthParam.expression = _widthInput.expression
            depthParam = params.itemById('depth')
            depthParam.expression = _depthInput.expression
            radiusParam = params.itemById('radius')
            radiusParam.expression = _radiusInput.expression

            # Update the feature.
            UpdatePocket(_editedCustomFeature)

            # Update the point dependency.
            dependency = _editedCustomFeature.dependencies.itemById('point')
            dependency.entity = point

            # Roll the timeline to its previous position.
            global _isRolledForEdit
            if _isRolledForEdit:
                _restoreTimelineObject.rollTo(False)
                _isRolledForEdit = False

            _editedCustomFeature = None

            showMessage('Finished ExecuteHandler')
        except:
            logger.exception('Exception')
            showMessage('Execute: {}\n'.format(traceback.format_exc()))


# Event handler for the executePreview event.
class ExecutePreviewHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        logger.debug('Execute Preview')
        try:
            eventArgs = adsk.core.CommandEventArgs.cast(args)        

            # Get the settings from the inputs.
            skPoint: adsk.fusion.SketchPoint = _pointSelectInput.selection(0).entity
            length = _lengthInput.value
            width = _widthInput.value
            depth = _depthInput.value
            radius = _radiusInput.value

            # Create the fillet feature.
            pocketBody = CreatePocketBody(skPoint.worldGeometry, length, width, depth, radius)

            # Create a base feature and add the body.
            face = GetFaceUnderPoint(skPoint.worldGeometry)
            paramBody = face.body
            comp = paramBody.parentComponent

            baseFeat = comp.features.baseFeatures.add()
            baseFeat.startEdit()
            comp.bRepBodies.add(pocketBody, baseFeat)
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
class PreSelectHandler(adsk.core.SelectionEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        logger.debug('PreSelect')
        try:
            eventArgs = adsk.core.SelectionEventArgs.cast(args)
            preSelectPoint: adsk.fusion.SketchPoint = eventArgs.selection.entity

            face = GetFaceUnderPoint(preSelectPoint.worldGeometry)
            if face is None:
                eventArgs.isSelectable = False
                return

            # Verify the body is not from an XRef.
            if preSelectPoint.assemblyContext:
                occ = preSelectPoint.assemblyContext
                if occ.isReferencedComponent:
                    eventArgs.isSelectable = False
                    return
        except:
            logger.exception('Exception')
            showMessage('PreSelectEventHandler: {}\n'.format(traceback.format_exc()))


# Event handler to handle the compute of the custom feature.
class ComputeCustomFeature(adsk.fusion.CustomFeatureEventHandler):
    def __init__(self):
        super().__init__()
    def notify(self, args):
        logger.debug('ComputeCustomFeature')
        try:
            global _updated
            if _updated:
                return
            _updated = True
            eventArgs: adsk.fusion.CustomFeatureEventArgs = args

            # Get the custom feature that is being computed.
            custFeature = eventArgs.customFeature

            # Get the original sketch point and the values from the custom feature.
            skPoint = custFeature.dependencies.itemById('point').entity
            length = custFeature.parameters.itemById('length').value
            width = custFeature.parameters.itemById('width').value
            depth = custFeature.parameters.itemById('depth').value
            radius = custFeature.parameters.itemById('radius').value

            # Create a new temporary body for the pocket. 
            # This can return None when the point isn't on a face.
            pocketBody = CreatePocketBody(skPoint.worldGeometry, length, 
                                          width, depth, radius)
            if pocketBody is None:
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
            baseFeature.updateBody(body, pocketBody)
            baseFeature.finishEdit()
        except:
            logger.exception('Exception')
            showMessage('CustomFeatureCompute: {}\n'.format(traceback.format_exc()))


# Utility function that given the position and pocket size builds
# a temporary B-Rep body is the tool body to create the pocket.
def CreatePocketBody(point, length, width, depth, radius):
    logger.debug('Creating pocketBody')
    try:
        # Get the face the point is on.
        face: adsk.fusion.BRepFace = GetFaceUnderPoint(point)
        if face is None:
            return None

        # Define the pocket at the origin with the length in the X direction,
        # width in the Y direction, and depth in the -Z direction.
        tBRep: adsk.fusion.TemporaryBRepManager = adsk.fusion.TemporaryBRepManager.get()
        lengthDir = adsk.core.Vector3D.create(1, 0, 0)
        widthDir = adsk.core.Vector3D.create(0, 1, 0)
        bodies = []
        lengthBox = adsk.core.OrientedBoundingBox3D.create(adsk.core.Point3D.create(0, 0, -depth / 2),
                                                           lengthDir, widthDir, length, width - (radius * 2), depth)
        bodies.append(tBRep.createBox(lengthBox))

        widthBox = adsk.core.OrientedBoundingBox3D.create(adsk.core.Point3D.create(0, 0, -depth / 2),
                                                           lengthDir, widthDir, length - (radius *2), width, depth)
        bodies.append(tBRep.createBox(widthBox))
        
        bodies.append(tBRep.createCylinderOrCone(adsk.core.Point3D.create((length / 2) - radius, (width / 2) - radius, 0), radius,
                                                 adsk.core.Point3D.create((length / 2) - radius, (width / 2) - radius, -depth), radius))                                                
        bodies.append(tBRep.createCylinderOrCone(adsk.core.Point3D.create((length / 2) - radius, (-width / 2) + radius, 0), radius,
                                                 adsk.core.Point3D.create((length / 2) - radius, (-width / 2) + radius, -depth), radius))
        bodies.append(tBRep.createCylinderOrCone(adsk.core.Point3D.create((-length / 2) + radius, (width / 2) - radius, 0), radius,
                                                 adsk.core.Point3D.create((-length / 2) + radius, (width / 2) - radius, -depth), radius))
        bodies.append(tBRep.createCylinderOrCone(adsk.core.Point3D.create((-length / 2) + radius, (-width / 2) + radius, 0), radius,
                                                 adsk.core.Point3D.create((-length / 2) + radius, (-width / 2) + radius, -depth), radius))

        # Combine the bodies into a single body.
        newBody: adsk.fusion.BRepBody = None
        for body in bodies:
            if newBody is None:
                newBody = body
            else:
                tBRep.booleanOperation(newBody, body, adsk.fusion.BooleanTypes.UnionBooleanType)

        # Get the natural U direction and normal of the face and use them as the length and depth directions.
        eval = face.evaluator
        (_, param) = eval.getParameterAtPoint(point)
        (_, normal) = eval.getNormalAtParameter(param)
        (_, lengthDir, _) = eval.getFirstDerivative(param)
        widthDir = normal.crossProduct(lengthDir)

        # Define a transform to position the pocket body onto the part.
        trans = adsk.core.Matrix3D.create()
        trans.setWithCoordinateSystem(point, lengthDir, widthDir, normal)
        tBRep.transform(newBody, trans)        

        return newBody
    except:
        logger.exception('Exception')
        showMessage('CreatePocketBody: {}\n'.format(traceback.format_exc()))


# Updates an existing custom pocket feature.
def UpdatePocket(customFeature: adsk.fusion.CustomFeature) -> bool:
    logger.debug('UpdatePocket')
    try:
        # Get the original sketch point and the values from the custom feature.
        skPoint: adsk.fusion.SketchPoint = customFeature.dependencies.itemById('point').entity
        length = customFeature.parameters.itemById('length').value
        width = customFeature.parameters.itemById('width').value
        depth = customFeature.parameters.itemById('depth').value
        radius = customFeature.parameters.itemById('radius').value

        # Create a new temporary body for the pocket. This can return None when the point isn't on a face.
        pocketBody = CreatePocketBody(skPoint.worldGeometry, length, width, depth, radius)
        if pocketBody is None:
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
        baseFeature.updateBody(body, pocketBody)
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
    des: adsk.fusion.Design = _app.activeProduct
    root = des.rootComponent

    foundFaces: adsk.core.ObjectCollection = root.findBRepUsingPoint(point, adsk.fusion.BRepEntityTypes.BRepFaceEntityType, 0.01, True)
    if foundFaces.count == 0:
        return None
    else:
        face: adsk.fusion.BRepFace = foundFaces.item(0)
        return face

    return None


def showMessage(message, error = False):
    textPalette: adsk.core.TextCommandPalette = _ui.palettes.itemById('TextCommands')
    textPalette.writeText(message)

    if error:
        _ui.messageBox(message)