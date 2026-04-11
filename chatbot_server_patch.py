# 這是要插入 chatbot_server.py 的 patch
# 在 robots.txt 路由後面加：

# daily.html 路由
# elif self.path == '/daily' or self.path == '/daily.html':
#     daily_file = BASE / 'public' / 'daily.html'
#     ...

# articles/ 路由  
# elif self.path.startswith('/articles/'):
#     article_path = BASE / self.path.lstrip('/')
#     ...
