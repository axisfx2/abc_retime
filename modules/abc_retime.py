# built in imports
import c4d
from math import floor

# tag/object ids
mograph_cache_tag = 1019337
point_cache_tag = 1021302
alembic_obj = c4d.Oalembicgenerator

class abc_retime(c4d.plugins.TagData):
    
    #self.SetOptimizeCache(False)

    # built in functions
    def __init__(self):
        pass

    def Init(self, op):
        self.InitAttr(op, int, c4d.ABC_START_FRAME)
        self.InitAttr(op, int, c4d.ABC_OFFSET)
        self.InitAttr(op, float, c4d.ABC_SPEED)
        self.InitAttr(op, bool, c4d.ABC_APPLY_CHILDREN)
        self.InitAttr(op, int, c4d.ABC_RESET_CHILDREN)

        # defaults
        op[c4d.ABC_SPEED] = 1.0

        bc = c4d.BaseContainer()

        return True

    def Execute(self, op, doc, obj, bt, priority, flags):
        if op is None:
            return c4d.EXECUTIONRESULT_OK

        # obj = op.GetObject()

        # set G variables
        self.op = op
        self.obj = obj

        self.doc = doc
        self.fps = doc.GetFps()
        self.doc_frame = doc.GetTime().GetFrame(self.fps)
        self.start_frame = op[c4d.ABC_START_FRAME]
        
        # calculate frame from speed
        _output, _mix = self.calcFrame()
        _output_basetime = _output
        
        # apply to objects
        if op[c4d.ABC_APPLY_CHILDREN]:
            for child in IterateHierarchy(obj):
                self.setTimeValue(child, _output_basetime)

        else:
            self.setTimeValue(obj, _output_basetime)

        # print('output', _output, _output_basetime.GetFrame(self.fps))

        return c4d.EXECUTIONRESULT_OK

    def Message(self, op, type, data):
        if type == c4d.MSG_DESCRIPTION_COMMAND:
            id = data.get('id')
            if id:
                id = id[0].id

                obj = op.GetObject()

                if id == c4d.ABC_START_FROM_DOC:
                    op[c4d.ABC_START_FRAME] = \
                        self.doc.GetLoopMinTime().GetFrame(self.fps)

                elif id == c4d.ABC_RESET_CHILDREN:
                    resetABC(obj)
                    print('reset children')

        return True

    def calcFrame(self):
        # self.op variables
        start_frame = self.start_frame
        offset = self.op[c4d.ABC_OFFSET]
        speed = self.op[c4d.ABC_SPEED]
        doc_frame = self.doc_frame
        single_frame = c4d.BaseTime(1, self.fps)

        start_time = c4d.BaseTime(start_frame, self.fps)
        doc_time = self.doc.GetTime()
        
        # return if playhead before start frame
        if doc_frame < start_frame:
            return start_time, 0.0
        
        _output = start_time

        ## read anim track and calculate frame offset (_output)

        # find speeds anim track
        speed_id = c4d.DescID(c4d.DescLevel(c4d.ABC_SPEED))
        speed_track = self.op.FindCTrack(speed_id)

        # existing anim track - read keyframes
        if speed_track:

            # check playhead is within the frame range
            if doc_frame > start_frame:
                keys = []

                breakout = False

                speed_curve = speed_track.GetCurve()

                cur_value = start_time

                # check value at start frame
                keys.append([
                    c4d.BaseTime(start_frame, self.fps),
                    speed_curve.GetValue(start_time)
                ])

                for k in range(speed_curve.GetKeyCount()):
                    # break when doc_frame has been found in prior loop
                    if breakout:
                        break

                    # get current keyframe values
                    key = speed_curve.GetKey(k)
                    time = key.GetTime()

                    # skip frames that exist before start frame
                    if time.GetFrame(self.fps) < start_frame:
                        continue

                    # skip frames that exist on the start frame
                    # we set this value before the loop
                    elif time.GetFrame(self.fps) == start_frame:
                        continue

                    # calculate inbetween frames
                    last_frame = keys[-1][0].GetFrame(self.fps) + 1
                    cur_frame = key.GetTime().GetFrame(self.fps)
                    t = []

                    for f in range(last_frame, (cur_frame + 1)):
                        t.append(f)
                        if f != start_frame:
                            cur_value += single_frame * c4d.BaseTime(speed_curve.GetValue(c4d.BaseTime(f, self.fps)))
                            keys.append([
                                c4d.BaseTime(f, self.fps),
                                cur_value
                            ])

                        if f == doc_frame:
                            _output = cur_value
                            breakout = True
                            break

                # add final sustain frame
                if not breakout:
                    s = keys[-1][0]
                    diff = doc_time - s
                    diff *= c4d.BaseTime(speed_curve.GetValue(s))

                    _output = cur_value + diff

        # no anim track - constant speed
        else:
            # check playhead is within the frame range
            if doc_frame > start_frame:
                diff = doc_time - start_time
                diff *= c4d.BaseTime(speed)

                _output = start_time + diff

        # apply post offset to _output
        _output += c4d.BaseTime(offset, self.fps)

        ## get mix values
        Min = floor(_output.GetFrame(self.fps))

        _mix = abs(_output.GetFrame(self.fps) - Min)
        # print(Min, _mix)
        # return (Min - start_frame), _mix
        return _output, _mix

    def setTimeValue(self, obj, _output):
        # no object
        if obj == None:
            return

        # mograph cache tag
        elif obj.GetTag(mograph_cache_tag):
            tag = obj.GetTag(1019337)
            tag[c4d.MGCACHETAG_OFFSET] = _output

        # point cache tag
        elif obj.GetTag(point_cache_tag):
            tag = obj.GetTag(1021302)
            tag[c4d.ID_CA_GEOMCACHE_TAG_CACHE_OFFSET] = _output

        # alembic
        elif obj.GetType() == alembic_obj:
            obj[c4d.ALEMBIC_USE_ANIMATION] = False
            obj[c4d.ALEMBIC_INTERPOLATION] = True
            obj[c4d.ALEMBIC_ANIMATION_FRAME] = _output

def resetABC(op):
    children = IterateHierarchy(op)

    for obj in children:
        if obj != op:
            if obj.GetType() == alembic_obj:
                c4d.CallButton(obj, c4d.ALEMBIC_ANIMATION_RESET)

# hierarchy iteration
# https://developers.maxon.net/?p=596
def GetNextObject(op):
    if op==None:
        return None
  
    if op.GetDown():
        return op.GetDown()
  
    while not op.GetNext() and op.GetUp():
        op = op.GetUp()
  
    return op.GetNext()
 
def IterateHierarchy(op):
    if op is None:
        return
 
    children = []

    while op:
        children.append(op)
        op = GetNextObject(op)
 
    return children