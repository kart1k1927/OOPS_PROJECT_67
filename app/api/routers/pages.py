from fastapi import APIRouter

#ADD your own endpoints here, this is just a template for auth endpoints

#v1 as prefix, for scalability, but it doesnt lowkey matter
router = APIRouter(prefix="/pages", tags=["pages"])

#add routes here, look at auth for example