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
    currentStatus = ndb.BooleanProperty()
    fridge = ndb.StructuredProperty(XYDataSet)
    fridgeAvg = ndb.FloatProperty()
    fridgeFreq = ndb.FloatProperty()
    ambient = ndb.StructuredProperty(XYDataSet)
    ambientAvg = ndb.FloatProperty()
    ambientFreq = ndb.FloatProperty()
    durForAvg = ndb.IntegerProperty()
    
    def dataForPlot(self):
        dataForPlot = '['
        
        for i in range(len(self.fridge.x)):
            dataForPlot += '[' + str(self.fridge.x[i]) + ',' + str(self.fridge.y[i]) + '],'
            
        #Remove the trailing comma
        dataForPlot = dataForPlot[:-1]
        
        #Close the list
        dataForPlot += ']'
        
        return dataForPlot
        
    def getAverage(self, series, timePeriod=3600):
        avg = 0
        startOfTimeRange = series.x[-1] - float(timePeriod)
        i = -1
        
        while series.x[i] >= startOfTimeRange and abs(i) < len(series.x):
            avg += (series.y[i] + series.y[i-1])/2 * (series.x[i] - series.x[i-1])
            i -= 1
            
        return avg / (series.x[-1] - series.x[i])
        
    def addMeasurement(self, series, time, measurement):
        time = float(time)
        measurement = float(measurement)
        
        if len(series.x) >= 1000:
            series.x = series.x[-999:]
            series.y = series.y[-999:]
        
        series.x.append(time)
        series.y.append(measurement)
        
    def getDashboardLink(self):
        return '/dashboard/' + self.key.urlsafe()
        
    def cleanData(self):
        i = 0
        pointsRemoved = 0
        
        while i < len(self.fridge.x):
            if self.fridge.x[i] == 0:
                self.fridge.x.pop(i)
                self.fridge.y.pop(i)
                self.ambient.x.pop(i)
                self.ambient.y.pop(i)
                
                pointsRemoved += 1
            else:
                i += 1
                
        return pointsRemoved
                
    
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
    def get(self, fsID, time, fridgeTemp, ambientTemp):
        key = ndb.Key(urlsafe=fsID)
        fs = key.get()
        
        fs.addMeasurement(fs.fridge, time, fridgeTemp)
        fs.addMeasurement(fs.ambient, time, ambientTemp)
            
        fs.put()
        
        self.response.write('Data point saved')
        self.response.write('>0  >0 >0>3>7')
        
class CleanData(webapp2.RequestHandler):
    def get(self, fsID):
        key = ndb.Key(urlsafe=fsID)
        fs = key.get()
        
        pointsRemoved = fs.cleanData()
        
        fs.put()
        
        
        self.response.write('Data cleaned, ' + str(pointsRemoved) + ' points removed.')
        

        
app = webapp2.WSGIApplication([
    webapp2.Route(r'/', handler=HomeHandler, name='home'),
    webapp2.Route(r'/dashboard/<fsID>', handler=DeviceDashboard, name='deviceDashboard'),
    webapp2.Route(r'/newFS', handler=AddFridgeSitter, name='addFridgeSitter'),
    webapp2.Route(r'/getFS/<fsID>', handler=GetFridgeSitter, name='GetFridgeSitter'),
    webapp2.Route(r'/saveDataPoint/<fsID>/<time>/<fridgeTemp>/<ambientTemp>', handler=SaveDataPoint, name='dataPoint'),
    webapp2.Route(r'/cleanData/<fsID>', handler=CleanData, name='cleanData')
])