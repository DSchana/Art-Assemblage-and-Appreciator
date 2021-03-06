from typing import Optional, List
from fastapi import FastAPI, status, HTTPException
from fastapi.responses import JSONResponse

from models.user import User, UserAuth
from models.art import Art, Assemblage

import os
import json
import uvicorn

art = FastAPI()

art_lock = False
art_json = {}


### Users

@art.post("/api/v1/user", status_code=status.HTTP_201_CREATED)
async def register_user(user_info: User):
    """Create new user and return an auth token. If the user already exists, this will also generate a
    new auth token for the user and invalidate the old one."""
    user_info.generateToken()
    user_info.encryptPassword()

    # Check if user already exists
    if user_info.username in art_json["users"]:
        # Grant new token if username and password are correct
        if user_info.password == art_json["users"][user_info.username]["password"]:
            user_info.the_art = art_json["users"][user_info.username]["the_art"]
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="username or password are incorrect")

    art_json["users"][user_info.username] = user_info.__dict__
    save_the_art()

    return { "token": user_info.token }

@art.put("/api/v1/user", status_code=status.HTTP_200_OK)
async def update_user(user_auth: UserAuth, new_user_info: User):
    """Change username or password using an auth token. Username and password are both
    needed in the `new_user_info`, even if only one is changing."""
    s, d = user_auth.authorize(art_json)
    if s != status.HTTP_200_OK:
        raise HTTPException(status_code=s, detail=d)

    new_user_info.encryptPassword()

    # Change username and password if something is different
    art_json["users"][new_user_info.username] = art_json["users"][user_auth.username]
    art_json["users"][new_user_info.username]["password"] = new_user_info.password

    save_the_art()

@art.delete("/api/v1/user", status_code=status.HTTP_200_OK)
async def remove_user(user_auth: UserAuth):
    """Delete user and all of their art collections."""
    s, d = user_auth.authorize(art_json)
    if s != status.HTTP_200_OK:
        raise HTTPException(status_code=s, detail=d)

    # Delete art collections
    for aid in art_json["users"][user_auth.username]["the_art"]:
        del art_json["arts"][aid]

    # Delete user
    del art_json["users"][user_auth.username]

    save_the_art()

@art.get("/api/v1/user/{username}", status_code=status.HTTP_200_OK)
async def get_user(username: str, token: str):
    """Get user info with authentication."""
    if username not in art_json["users"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user does not exist")
    if art_json["users"][username]["token"] != token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid auth token")

    return {
        "username": username,
        "the_art": art_json["users"][username]["the_art"]
    }


### The Art

@art.post("/api/v1/assemblage", status_code=status.HTTP_201_CREATED)
async def create_assemblage(user_auth: UserAuth, a_name: str):
    """Create new art assemblage under the authenticating user with the name `a_name`."""
    s, d = user_auth.authorize(art_json)
    if s != status.HTTP_200_OK:
        raise HTTPException(status_code=s, detail=d)

    a = Assemblage()
    a.name = a_name

    art_json["arts"][a.id] = a.__dict__
    art_json["users"][user_auth.username]["the_art"].append(a.id)

    save_the_art()

    return { "id": a.id }

@art.delete("/api/v1/assemblage", status_code=status.HTTP_200_OK)
async def delete_assemblage(user_auth: UserAuth, aid: str):
    """Delete assemblage with `id = aid` if the authenticating user owns it."""
    s, d = user_auth.authorize(art_json)
    if s != status.HTTP_200_OK:
        raise HTTPException(status_code=s, detail=d)
    
    if aid not in art_json["users"][user_auth.username]["the_art"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This user does not own the collection of art")

    art_json["users"][user_auth.username]["the_art"].remove(aid)
    del art_json["arts"][aid]

    save_the_art()

@art.put("/api/v1/assemblage/{aid}", status_code=status.HTTP_200_OK)
async def update_assemblage(aid:str, user_auth: UserAuth, a_name: str):
    """Change the name of the assemblage."""
    s, d = user_auth.authorize(art_json)
    if s != status.HTTP_200_OK:
        raise HTTPException(status_code=s, detail=d)
    
    if aid not in art_json["users"][user_auth.username]["the_art"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This user does not own the collection of art")

    art_json["arts"][aid]["name"] = a_name

    save_the_art()

@art.post("/api/v1/assemblage/{aid}", status_code=status.HTTP_201_CREATED)
async def add_art(aid: str, user_auth: UserAuth, art_list: List[Art]):
    """Add works of art to assemblage by reference hosted location."""
    s, d = user_auth.authorize(art_json)
    if s != status.HTTP_200_OK:
        raise HTTPException(status_code=s, detail=d)
    
    if aid not in art_json["users"][user_auth.username]["the_art"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This user does not own the collection of art")

    art_json["arts"][aid]["art"] += [art.__dict__ for art in art_list]

    save_the_art()

@art.delete("/api/v1/assemblage/{aid}", status_code=status.HTTP_200_OK)
async def remove_art(aid: str, user_auth: UserAuth, art_list: List[str]):
    """Delete works of art by name or hosted location"""
    s, d = user_auth.authorize(art_json)
    if s != status.HTTP_200_OK:
        raise HTTPException(status_code=s, detail=d)
    
    if aid not in art_json["users"][user_auth.username]["the_art"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This user does not own the collection of art")

    to_remove = []
    for art_id in art_list:
        for i in range(len(art_json["arts"][aid]["art"])):
            art: Art = art_json["arts"][aid]["art"][i]
            if art_id == art["name"] or art_id == art["src"]:
                to_remove.append(i)
                break
    
    to_remove.sort(reverse=True)
    for r in to_remove:
        del art_json["arts"][aid]["art"][r]

    save_the_art()


### Public access
# No need for an account to view art; art is for everyone

@art.get("/api/v1/assemblage", status_code=status.HTTP_200_OK)
async def get_assemblage(_id: str = "", name: str = None):
    """Get full assemblage of art works by name or id."""
    ret = []

    for id, assemblage in art_json["arts"].items():
        if _id == id or name != None and name in assemblage["name"]:
            ret.append(assemblage)

    return ret

@art.get("/api/v1/art", status_code=status.HTTP_200_OK)
async def get_art(name: str = None, src: str = None, tags: List[str] = []):
    """Find individual works of art by name, hosting source or descriptive tag."""
    ret = []

    for assemblage in art_json["arts"].values():
        for art in assemblage["art"]:
            # Find matching art name or src
            if name != None and name in art["name"] or art["src"] == src:
                ret.append(art)
            else:
                # Find matching tags
                for tag in tags:
                    if tag in art["tags"]:
                        ret.append(art)

    return ret


def save_the_art():
    """Save json to file for permanent storage"""

    global art_lock

    while (art_lock):
        continue

    art_lock = True

    with open("databases/art_assemblage.json", 'w') as f:
        f.write(json.dumps(art_json))

    art_lock = False


# Check for storage files
if not os.path.exists("databases"):
    os.system("mkdir databases")
if not os.path.exists("databases/art_assemblage.json"):
    os.system("touch databases/art_assemblage.json")

# Load data file from storage into memory for faster access
# For the small scale use this project will see, a JSON file is much faster and optimal.
# However, for scaling I would convert this to an SQL database
with open("databases/art_assemblage.json", 'r') as f:
    try:
        art_json = json.loads(f.read().strip())
    except Exception as e:
        art_json = {}

    if "users" not in art_json:
        art_json["users"] = {}
    
    if "arts" not in art_json:
        art_json["arts"] = {}

save_the_art()

if __name__ == "__main__":
    uvicorn.run(art)
