import azure.functions as func

from app import app as fastapi_app
# from main import app fastapi_app 

app = func.AsgiFunctionApp(app=fastapi_app,http_auth_level=func.AuthLevel.ANONYMOUS)
