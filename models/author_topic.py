from app import db

from models.topic import as_topic_openalex_id
from models.topic import Topic


class AuthorTopic(db.Model):
    __table_args__ = {'schema': 'counts'}
    __tablename__ = "author_topic_for_api_full"

    author_id = db.Column(db.BigInteger, db.ForeignKey("mid.author.author_id"), primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey("mid.topic.topic_id"), primary_key=True)
    topic_count = db.Column(db.Integer)
    topic_share = db.Column(db.Float)

    def to_dict(self, return_level="full"):
        response = Topic.query.get(self.topic_id).to_dict(return_level)
        if return_level == "count":
            response["count"] = self.topic_count
        elif return_level == "share":
            response["value"] = round(self.topic_share, 7)
        return response

    def __repr__(self):
        return "<AuthorTopic ( {} ) {}>".format(self.author_id, self.topic_id)
