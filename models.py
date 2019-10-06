from peewee import *


db = SqliteDatabase('telegram_bot.db')


class BaseModel(Model):
    class Meta:
        database = db

class Mark(BaseModel):

    mark_name = CharField()
    mark_description = CharField()

class Branch(BaseModel):

    branch_name = CharField()
    branch_description = CharField()

class Favorite(BaseModel):
    favorite_branch = CharField()


