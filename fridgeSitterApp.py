import cgi
import os
import urllib

from google.appengine.api import users
from google.appengine.ext import ndb
#import matplotlib.pyplot as plt
#import numpy as np
import cStringIO
import jinja2
import webapp2
import time

ADDFS_FORM_HTML = """\
<form action="/newFS" method="post">
    <div><textarea name="fsName" rows="3" cols="60"></textarea></div>
    <div><input type="submit" value="Add Device"></div>
</form>
"""

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class XYDataSet(ndb.Model):
    '''Models a list of data points'''
    name = ndb.StringProperty()
    x = ndb.FloatProperty(repeated=True)
    y = ndb.FloatProperty(repeated=True)

class FridgeSitter(ndb.Model):
    """Models an individual Fridge Sitter device."""
    name = ndb.StringProperty()
    owner = ndb.StringProperty()
    fridgeStatus = ndb.BooleanProperty()
    fridge = ndb.StructuredProperty(XYDataSet)
    fridgeAvg = ndb.FloatProperty()
    fridgeFreq = ndb.FloatProperty()
    fridgeMin = ndb.FloatProperty()
    fridgeMax = ndb.FloatProperty()
    ambientStatus = ndb.BooleanProperty()
    ambient = ndb.StructuredProperty(XYDataSet)
    ambientAvg = ndb.FloatProperty()
    ambientFreq = ndb.FloatProperty()
    ambientMin = ndb.FloatProperty()
    ambientMax = ndb.FloatProperty()
    loggingInt = ndb.FloatProperty()
    durForAvg = ndb.IntegerProperty()
    tempSets = ndb.StringProperty()
    
    def dataForPlot(self, timeSpan=240):
        i = -1
        timeSpanEnd = self.fridge.x[-1]
        timeSpanStart = timeSpanEnd - timeSpan*60
        
        
        while abs(i) < len(self.fridge.x) and timeSpanStart <= self.fridge.x[i]:
            i -= 1
            
        
        dataForPlot = '['
        
        while i < 0:
            dataForPlot += '[new Date(' + str(self.fridge.x[i]*1000) + '),' + str(self.fridge.y[i]) + '],'
            i += 1
            
        #Remove the trailing comma
        dataForPlot = dataForPlot[:-1]
        
        #Close the list
        dataForPlot += ']'
        
        return dataForPlot
        
    def getAverage(self, series, timePeriod=3600):
        if len(series.x) == 0:
            return 0.
        elif len(series.x) == 1:
            return series.y[0]
        else:
            avg = 0
            startOfTimeRange = series.x[-1] - float(timePeriod)
            i = -1
            
            while series.x[i] >= startOfTimeRange and abs(i) < len(series.x):
                avg += (series.y[i] + series.y[i-1])/2 * (series.x[i] - series.x[i-1])
                i -= 1
                
            return avg / (series.x[-1] - series.x[i])
        
    def addMeasurement(self, series, measTime, measurement):
        measTime = float(measTime)
        measurement = float(measurement)
        
        if len(series.x) >= 1000:
            series.x = series.x[-999:]
            series.y = series.y[-999:]
        
        series.x.append(measTime)
        series.y.append(measurement)
        
        self.updateStatus()
        
    def updateStatus(self):
        self.fridgeAvg = self.getAverage(self.fridge)
        self.ambientAvg = self.getAverage(self.ambient)
        
        self.fridgeStatus = self.fridgeMin <= self.fridgeAvg and self.fridgeAvg <= self.fridgeMax
        self.ambientStatus = self.ambientMin <= self.ambientAvg and self.ambientAvg <= self.ambientMax
        
    def getDashboardLink(self):
        return '/dashboard/' + self.key.urlsafe()
        
    def getLoggingInt(self):
        return self.loggingInt
        
    def cleanData(self, timeIndex):
        i = 0
        pointsRemoved = 0
        
        while i < len(self.fridge.x):
            if self.fridge.x[i] <= timeIndex:
                self.fridge.x.pop(i)
                self.fridge.y.pop(i)
                self.ambient.x.pop(i)
                self.ambient.y.pop(i)
                
                pointsRemoved += 1
            else:
                i += 1
                
        return pointsRemoved
        
    def removeDataPoint(self, timeIndex):
        i = 0
        
    
        while i < len(self.fridge.x):
            if self.fridge.x[i] == timeIndex:
                self.fridge.x.pop(i)
                self.fridge.y.pop(i)
                self.ambient.x.pop(i)
                self.ambient.y.pop(i)
                
                return True
                
            else:
                i += 1
                
    
class FSOwner(ndb.Model):
    '''Models the owner of one or more fridge sitter devices'''
    userID = ndb.StringProperty()
    fridgeSitters = ndb.KeyProperty(repeated=True)
    
class HomeHandler(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        
        template_values = {
            'user' : user
        }
        
        if user:
            template_values['logoutURL'] = users.create_logout_url('/')
            qry = FridgeSitter.query(FridgeSitter.owner == user.user_id())
            template_values['fridgeSitters'] = qry.fetch(100)
        else:
            template_values['loginURL'] = users.create_login_url('/')
        
        
        template = JINJA_ENVIRONMENT.get_template('home.html')
        self.response.write(template.render(template_values))  
        
class AddDevice(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        
        template_values = {
            'user': user,
            'get': True
        }
        
        if user:
            template_values['logoutURL'] = users.create_logout_url('/')
        
        template = JINJA_ENVIRONMENT.get_template('addDevice.html')
        self.response.write(template.render(template_values))

        
    def post(self):
        user = users.get_current_user()
        
        template_values = {
            'user': user,
            'get': False
        }
        
        if user:
            template_values['logoutURL'] = users.create_logout_url('/')
            
            newFS = FridgeSitter(name=self.request.get('name'),owner=user.user_id())
            newFS.fridgeMin = float(self.request.get('fridgeMin'))
            newFS.fridgeMax = float(self.request.get('fridgeMax'))
            newFS.ambientMin = float(self.request.get('ambientMin'))
            newFS.ambientMax = float(self.request.get('ambientMax'))
            newFS.loggingInt = float(self.request.get('checkInInt'))
            newFS.tempSets = str(self.request.get('tempSets'))
            newFS.fridge = XYDataSet(x=[],y=[])
            newFS.ambient = XYDataSet(x=[],y=[])
            newFS_key = newFS.put()
            
            template_values['activeFridgeSitter'] = newFS_key.get()
            
        template = JINJA_ENVIRONMENT.get_template('addDevice.html')
        self.response.write(template.render(template_values))
            
        
class AddFridgeSitter(webapp2.RequestHandler):
    def post(self):
        user = users.get_current_user()
        if user:
            newFS = FridgeSitter(name=self.request.get('fsName'),owner=user.user_id(), currentStatus=False)
            newFS.fridge = XYDataSet(x=[],y=[])
            newFS.ambient = XYDataSet(x=[],y=[])
            newFS_key = newFS.put()
            
            self.response.write(newFS_key.urlsafe())
        else:
            greeting = ('<a href="%s">Sign in or register</a>.' %
                        users.create_login_url('/'))

            self.response.out.write('<html><body>%s</body></html>' % greeting)
            
class DeviceDashboard(webapp2.RequestHandler):
    def get(self, fsID):
        user = users.get_current_user()
        
        if user:
            qry = FridgeSitter.query(FridgeSitter.owner == user.user_id())
            template_values = {
                'user': user,
                'logoutURL': users.create_logout_url('/'),
                'activeFridgeSitter': ndb.Key(urlsafe=fsID).get(),
                'fridgeSitters': qry.fetch(100)
            }
            
            template = JINJA_ENVIRONMENT.get_template('dashboard.html')
            
        else:
            template_values = {
                'user': user,
                'loginURL': users.create_login_url('/')
            }
            
            template = JINJA_ENVIRONMENT.get_template('home.html')
            
        self.response.write(template.render(template_values))
            
class GetFridgeSitter(webapp2.RequestHandler):
    def get(self, fsID):
        key = ndb.Key(urlsafe=fsID)
        fs = key.get()
        self.response.write(fs)
    
class SaveDataPoint(webapp2.RequestHandler):
    def get(self, fsID, measTime, temp1, temp2):
        if fsID == 'ahVzfmFlc3RoZXRpYy1maWJlci03ODlyGQsSDEZyaWRnZVNpdHRlchiAgICAvJ-bCgw':
            fsID = 'ahVzfmFlc3RoZXRpYy1maWJlci03ODlyGQsSDEZyaWRnZVNpdHRlchiAgIDAyN6VCgw'
        
        key = ndb.Key(urlsafe=fsID)
        fs = key.get()
        
        if float(measTime) == 0:
            measTime = time.time()
        
        if fs.tempSets == '01':
            fs.addMeasurement(fs.fridge, measTime, temp1)
            fs.addMeasurement(fs.ambient, measTime, temp2)
        else:
            fs.addMeasurement(fs.ambient, measTime, temp1)
            fs.addMeasurement(fs.fridge, measTime, temp2)
            
        sleepIterations = str(int(float(fs.loggingInt) * 60 / 8))
        j = 0
        
        statusCode = ''
        
        for i in range(10):
            if i%2 == 0:
                statusCode += '>'
            elif i > 10 - 2*len(sleepIterations):
                statusCode += sleepIterations[j]
                j += 1
            else:
                statusCode += '0'
            
        fs.put()
        
        self.response.write('Data point saved')
        self.response.write(statusCode)
        
class CleanData(webapp2.RequestHandler):
    def get(self, fsID, timeIndex):
        key = ndb.Key(urlsafe=fsID)
        fs = key.get()
        
        pointsRemoved = fs.cleanData(int(timeIndex))
        
        fs.put()
        
        
        self.response.write('Data cleaned, ' + str(pointsRemoved) + ' points removed.')
        
class RemoveDataPoint(webapp2.RequestHandler):
    def get(self, fsID, timeIndex):
        key = ndb.Key(urlsafe=fsID)
        fs = key.get()
        
        if fs.removeDataPoint(int(timeIndex)):
        
            fs.put()
            
            
            self.response.write('Datapoint removed.')
        
        else:
            self.response.write('Datapoint not found!')
        
        
        
class Sign(webapp2.RequestHandler):
    def post(self):
        self.response.write(self.request.get('last'))
        self.response.write(self.request.get('first'))
        
class Form(webapp2.RequestHandler):
    def get(self):
        template_values = {}
        template = JINJA_ENVIRONMENT.get_template('addDevice.html')
        self.response.write(template.render(template_values)) 
        

        
app = webapp2.WSGIApplication([
    webapp2.Route(r'/', handler=HomeHandler, name='home'),
    webapp2.Route(r'/dashboard/<fsID>', handler=DeviceDashboard, name='deviceDashboard'),
    webapp2.Route(r'/addDevice', handler=AddDevice, name='addDevice'),
    webapp2.Route(r'/newFS', handler=AddFridgeSitter, name='addFridgeSitter'),
    webapp2.Route(r'/getFS/<fsID>', handler=GetFridgeSitter, name='GetFridgeSitter'),
    webapp2.Route(r'/saveDataPoint/<fsID>/<measTime>/<temp1>/<temp2>', handler=SaveDataPoint, name='dataPoint'),
    webapp2.Route(r'/cleanData/<fsID>/<timeIndex>', handler=CleanData, name='cleanData'),
    webapp2.Route(r'/removeDataPoint/<fsID>/<timeIndex>', handler=RemoveDataPoint, name='removeDataPoint'),
    webapp2.Route(r'/form', handler=Form, name='form'),
    webapp2.Route(r'/sign', handler=Sign, name='sign')
])