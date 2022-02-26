from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

class ServerDB:
    Base = declarative_base()

    class AllUsers(Base):
        __tablename__ = 'all_users'
        id = Column(Integer, primary_key=True)
        login = Column(String, unique=True)
        last_conn = Column(DateTime)

        def __init__(self, login):
            self.login = login
            self.last_conn = datetime.datetime.now()

    class ActiveUsers(Base):
        __tablename__ = 'active_users'
        id = Column(Integer, primary_key=True)
        user = Column(String, ForeignKey('all_users.id'), unique=True)
        ip = Column(String)
        port = Column(Integer)
        time_conn = Column(DateTime)

        def __init__(self, user, ip, port, time_conn):
            self.user = user
            self.ip = ip
            self.port = port
            self.time_conn = time_conn

    class LoginHistory(Base):
        __tablename__ = 'login_history'
        id = Column(Integer, primary_key=True)
        user = Column(String, ForeignKey('all_users.id'))
        ip = Column(String)
        port = Column(Integer)
        last_conn = Column(DateTime)

        def __init__(self, user, ip, port, last_conn):
            self.user = user
            self.ip = ip
            self.port = port
            self.last_conn = last_conn

    def __init__(self):
        self.engine = create_engine('sqlite:///server_base.db3', echo=False, pool_recycle=7200)
        self.Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        # Очистка таблицы активных пользователей при соединении
        self.session.query(self.ActiveUsers).delete()
        self.session.commit()

    # Функция выполняется при входе пользователя. Фиксирует в базе факт входа.
    def user_login(self, username, ip_address, port):
        # Запрос в таблицу пользователей на наличие там такого пользователя
        rez = self.session.query(self.AllUsers).filter_by(login=username)
        # Если имя пользователя уже присутствует в таблице, обновляем время последнего входа.
        if rez.count():
            user = rez.first()
            user.last_conn = datetime.datetime.now()
        # Если нет, то создаем нового пользователя
        else:
            user = self.AllUsers(username)
            self.session.add(user)
            self.session.commit()

        # Теперь нужно создать запись в таблицу активных пользователей о факте входа.
        new_active_user = self.ActiveUsers(user.id, ip_address, port, datetime.datetime.now())
        self.session.add(new_active_user)

        # + сохранить в историю входов.
        history = self.LoginHistory(user.id, ip_address, port, datetime.datetime.now())
        self.session.add(history)

        self.session.commit()

    def user_logout(self, username):
        # Запрос выходящего пользователя
        user = self.session.query(self.AllUsers).filter_by(login=username).first()
        # Удаление из таблицы активных пользователей
        self.session.query(self.ActiveUsers).filter_by(user=user.id).delete()
        self.session.commit()

    # Функция возвращает список известных пользователей со временем последнего входа.
    def users_list(self):
        query = self.session.query(
            self.AllUsers.login,
            self.AllUsers.last_conn,
        )
        return query.all()

    # Фунцкция возвращает список активных пользователей
    def active_users_list(self):
        query = self.session.query(
            self.AllUsers.login,
            self.ActiveUsers.ip,
            self.ActiveUsers.port,
            self.ActiveUsers.time_conn
        ).join(self.AllUsers)

        return query.all()

    # Функция возвращает историю входа по пользователю или всем пользователям.
    def login_history(self, username = None):
        query = self.session.query(self.AllUsers.login,
                                   self.LoginHistory.last_conn,
                                   self.LoginHistory.ip,
                                   self.LoginHistory.port
                                   ).join(self.AllUsers)
        if username:
            query = query.filter(self.AllUsers.login == username)
        return query.all()

if __name__ == '__main__':
    db = ServerDB()
    db.user_login('client_1', '192.168.1.4', 8888)
    db.user_login('client_2', '192.168.1.4', 7777)
    # Выводим список кортежей - активных пользователей
    print(db.active_users_list())
    # Выполняем отключение пользователя
    # db.user_logout('client_1')
    # print(db.users_list())
    # # выводим список активных пользователей
    # print(db.active_users_list())
    # db.user_logout('client_2')
    # print(db.users_list())
    # print(db.active_users_list())
