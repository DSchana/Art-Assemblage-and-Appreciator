import base64
import hashlib
import uuid

from typing import Optional, List
from pydantic import BaseModel
from fastapi import status

class User(BaseModel):
    username: str
    password: str
    token: Optional[str] = None
    the_art: Optional[List[str]] = []

    def generateToken(self):
        self.token = str(uuid.uuid4())
        return self.token

    def encryptPassword(self):
        self.password = str(hashlib.sha224(self.password.encode('utf-8')).hexdigest())

class UserAuth(BaseModel):
    username: str
    token: str

    def authorize(self, art_json):
        if self.username not in art_json["users"]:
            return (status.HTTP_404_NOT_FOUND, "user does not exist")
        if art_json["users"][self.username]["token"] != self.token:
            return (status.HTTP_401_UNAUTHORIZED, "invalid auth token")

        return (status.HTTP_200_OK, "Authorization successful")
