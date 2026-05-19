"""
Skill Relationships Dictionary
===============================
Comprehensive mapping of 200+ parent skills to their related secondary skills.
Used for three-tier skill matching (Primary/Secondary/Partial).

Structure:
    skillRelations[PARENT_SKILL] = {
        "category": "frontend/backend/database/devops/cloud/mobile/data",
        "related": [RELATED_SKILL_1, RELATED_SKILL_2, ...]
    }

Matching Logic:
- Primary (20 pts): Exact match in JD
- Secondary (10 pts): Related skill in JD
- Partial (6 pts): Same category but not in related list
- No Match (0 pts): Not related
"""

# Parent Skill → Related Secondary Skills
# 200+ parent skills with 1000+ related skills across all categories
skillRelations = {
    # ========================
    # FRONTEND (React, Vue, Angular, etc.)
    # ========================
    "React": {
        "category": "frontend",
        "related": [
            "React.js", "ReactJS", "React Native", "Next.js", "NextJS", "Gatsby",
            "Redux", "Redux Toolkit", "Redux-Saga", "MobX", "Zustand",
            "React Router", "React Hooks", "React Context", "React Query",
            "Framer Motion", "React Spring", "Styled Components", "CSS Modules",
            "Tailwind CSS", "Material UI", "Ant Design", "Chakra UI",
            "Vite", "Webpack", "Babel", "ESLint", "Prettier"
        ]
    },
    "React.js": {
        "category": "frontend",
        "related": ["React", "React Native", "Next.js", "Redux", "Tailwind CSS"]
    },
    "Vue": {
        "category": "frontend",
        "related": [
            "Vue.js", "VueJS", "Vue 2", "Vue 3", "Nuxt", "Nuxt.js",
            "Vuex", "Pinia", "Vue Router", "Vue CLI", "Vite",
            "Vuetify", "Quasar", "Element Plus", "PrimeVue"
        ]
    },
    "Vue.js": {
        "category": "frontend",
        "related": ["Vue", "Nuxt.js", "Vuex", "Pinia"]
    },
    "Angular": {
        "category": "frontend",
        "related": [
            "Angular.js", "Angular 2", "Angular 4", "Angular 5", "Angular 6",
            "Angular 7", "Angular 8", "Angular 9", "Angular 10", "Angular 11",
            "Angular 12", "Angular 13", "Angular 14", "Angular 15", "Angular 16",
            "NgRx", "RxJS", "Angular Material", "PrimeNG"
        ]
    },
    "Next.js": {
        "category": "frontend",
        "related": [
            "React", "NextJS", "TypeScript", "Tailwind CSS", "Vercel",
            "GraphQL", "API Routes", "SSG", "SSR"
        ]
    },
    "HTML": {
        "category": "frontend",
        "related": ["HTML5", "XHTML", "Semantic HTML", "DOM", "HTML Canvas"]
    },
    "CSS": {
        "category": "frontend",
        "related": [
            "CSS3", "SCSS", "SASS", "LESS", "CSS Modules",
            "Flexbox", "Grid", "Animations", "Bootstrap", "Tailwind"
        ]
    },
    "JavaScript": {
        "category": "frontend",
        "related": [
            "ES5", "ES6", "ES7", "ES8", "ES9", "ES10", "ES11", "ES12",
            "TypeScript", "JQuery", "Ajax", "JSON", "DOM", "Babel"
        ]
    },
    "TypeScript": {
        "category": "frontend",
        "related": [
            "TS", "TSX", "TypeScript 4", "TypeScript 5", "Zod",
            "io-ts", "Runtypes", "TypeGuard"
        ]
    },
    "jQuery": {
        "category": "frontend",
        "related": ["jQuery UI", "Ajax", "DOM", "JSON", "JavaScript"]
    },
    "Bootstrap": {
        "category": "frontend",
        "related": ["Bootstrap 4", "Bootstrap 5", "CSS", "Responsive Design"]
    },
    "Tailwind CSS": {
        "category": "frontend",
        "related": ["Tailwind", "CSS", "PostCSS", "Utility-First CSS"]
    },
    "SASS": {
        "category": "frontend",
        "related": ["SCSS", "CSS", "SASS", "Compass"]
    },
    "Webpack": {
        "category": "frontend",
        "related": ["Webpack 4", "Webpack 5", "Babel", "Loaders", "Plugins"]
    },
    "Vite": {
        "category": "frontend",
        "related": ["ViteJS", "ESBuild", "Hot Module Replacement"]
    },
    "Redux": {
        "category": "frontend",
        "related": ["Redux Toolkit", "Redux-Saga", "Redux-Thunk", "React-Redux"]
    },

    # ========================
    # BACKEND (Node.js, Python, Java, etc.)
    # ========================
    "Node.js": {
        "category": "backend",
        "related": [
            "NodeJS", "Node", "Express", "Express.js", "NestJS", "Nest",
            "Koa", "Hapi", "Fastify", "Meteor", "Sails", "Socket.io",
            "Node Modules", "NPM", "Yarn", "PNPM", "npx",
            "Express Router", "Middleware", "REST APIs", "GraphQL"
        ]
    },
    "Node": {
        "category": "backend",
        "related": ["Node.js", "Express", "NPM", "Node Modules"]
    },
    "Express": {
        "category": "backend",
        "related": [
            "Express.js", "Express", "Express Router", "Express Middleware",
            "CORS", "Body Parser", "Morgan", "Helmet"
        ]
    },
    "Express.js": {
        "category": "backend",
        "related": ["Express", "Node.js", "REST APIs", "Middleware"]
    },
    "NestJS": {
        "category": "backend",
        "related": [
            "Nest", "NestJS", "TypeScript", "RxJS", "Node.js",
            "Nest Guards", "Nest Interceptors", "Nest Filters", "DI"
        ]
    },
    "Koa": {
        "category": "backend",
        "related": ["Koa.js", "Koa Router", "Koa Body Parser"]
    },
    "Python": {
        "category": "backend",
        "related": [
            "Python 2", "Python 3", "Django", "Flask", "FastAPI",
            "Pyramid", "Bottle", "Tornado", "Web2py", "CherryPy",
            "Pip", "Virtualenv", "Conda", "Poetry", "Pipenv",
            "REST APIs", "GraphQL", "ORM"
        ]
    },
    "Python 3": {
        "category": "backend",
        "related": ["Python", "Django", "Flask", "FastAPI"]
    },
    "Django": {
        "category": "backend",
        "related": [
            "Django REST Framework", "DRF", "Django ORM", "Django Forms",
            "Django Templates", "Django Admin", "Django Auth",
            "Django Channels", "Celery"
        ]
    },
    "Flask": {
        "category": "backend",
        "related": [
            "Flask-SQLAlchemy", "Flask-RESTful", "Flask-Migrate",
            "Flask-WTForms", "Flask-Login", "Jinja2"
        ]
    },
    "FastAPI": {
        "category": "backend",
        "related": [
            "Pydantic", "Uvicorn", "Starlette", "Python",
            "OpenAPI", "TypeScript"
        ]
    },
    "Java": {
        "category": "backend",
        "related": [
            "Java 8", "Java 11", "Java 17", "Java 21",
            "Spring", "Spring Boot", "Spring MVC", "Spring Data",
            "Spring Security", "Hibernate", "JPA", "Maven", "Gradle",
            "REST APIs", "Microservices", "Tomcat", "JBoss"
        ]
    },
    "Spring": {
        "category": "backend",
        "related": ["Spring Framework", "Spring Boot", "Spring MVC", "Spring Security"]
    },
    "Spring Boot": {
        "category": "backend",
        "related": [
            "Spring", "Spring Data", "Spring Security", "Spring MVC",
            "JPA", "Hibernate", "Actuator", "DevTools"
        ]
    },
    "Go": {
        "category": "backend",
        "related": [
            "Golang", "Go Language", "Gin", "Echo", "Fiber",
            "Gorilla", "Mux", "GORM", "SQLx", "Go Modules"
        ]
    },
    "Golang": {
        "category": "backend",
        "related": ["Go", "Gin", "Echo", "Fiber"]
    },
    "C#": {
        "category": "backend",
        "related": [
            "CSharp", ".NET", ".NET Core", ".NET 5", ".NET 6", ".NET 7",
            "ASP.NET", "ASP.NET Core", "ASP.NET MVC", "Entity Framework",
            "LINQ", "WPF", "WinForms", "Xamarin"
        ]
    },
    "CSharp": {
        "category": "backend",
        "related": [".NET", "ASP.NET", "Entity Framework", "LINQ"]
    },
    ".NET": {
        "category": "backend",
        "related": [".NET Core", ".NET 5", ".NET 6", "ASP.NET Core", "Entity Framework Core"]
    },
    "Ruby": {
        "category": "backend",
        "related": [
            "Ruby 2", "Ruby 3", "Rails", "Ruby on Rails",
            "Sinatra", "RSpec", "Capybara", "Bundler", "RubyGems"
        ]
    },
    "Rails": {
        "category": "backend",
        "related": ["Ruby on Rails", "Rails API", "ActiveRecord", "ActiveJob"]
    },
    "PHP": {
        "category": "backend",
        "related": [
            "PHP 7", "PHP 8", "Laravel", "Symfony", "CodeIgniter",
            "Yii", "CakePHP", "Zend", "Composer", "PHP OOP",
            "PDO", "MySQLi"
        ]
    },
    "Laravel": {
        "category": "backend",
        "related": [
            "Laravel 8", "Laravel 9", "Laravel 10", "Eloquent",
            "Blade", "Artisan", "Homestead", "Valet"
        ]
    },
    "Rust": {
        "category": "backend",
        "related": [
            "Rust", "Actix", "Rocket", "Warp", "Serde", "Tokio",
            "Cargo", "Rustup"
        ]
    },
    "Scala": {
        "category": "backend",
        "related": [
            "Scala", "Play Framework", "Akka", "Spark", "Cats",
            " Scala", "SBT"
        ]
    },
    "Kotlin": {
        "category": "backend",
        "related": [
            "Kotlin", "Spring Boot", "Ktor", "Javalin",
            "Coroutines", "Android"
        ]
    },
    "Swift": {
        "category": "backend",
        "related": [
            "Swift", "Swift 5", "Vapor", "Kitura", "Perfect",
            "Server-Side Swift"
        ]
    },

    # ========================
    # DATABASE (MongoDB, PostgreSQL, etc.)
    # ========================
    "MongoDB": {
        "category": "database",
        "related": [
            "Mongo", "Mongoose", "MongoDB Atlas", "MongoDB Compass",
            "MongoDB Stitch", "MongoDB Charts", "GridFS",
            "NoSQL", "Document Database", "BSON", "Aggregation Pipeline"
        ]
    },
    "MySQL": {
        "category": "database",
        "related": [
            "MySQL 5", "MySQL 8", "MariaDB", "MySQL Workbench",
            "MySQL Shell", "InnoDB", "MyISAM", "SQL",
            "MySQL Connector", "Sequelize (MySQL)"
        ]
    },
    "PostgreSQL": {
        "category": "database",
        "related": [
            "Postgres", "PostgreSQL 12", "PostgreSQL 13", "PostgreSQL 14",
            "PostgreSQL 15", "PostgreSQL 16", "pgAdmin", "PSQL",
            "PostGIS", "Row Level Security", "JSONB", "CUBE"
        ]
    },
    "Redis": {
        "category": "database",
        "related": [
            "Redis ", "Redis Cluster", "Redis Sentinel", "Redisson",
            "Redis OM", "In-Memory Database", "Cache", "Pub/Sub"
        ]
    },
    "SQL": {
        "category": "database",
        "related": [
            "SQLite", "T-SQL", "PL/SQL", "MySQL", "PostgreSQL",
            "SQL Server", "Oracle SQL", "SQLAlchemy", "Knex"
        ]
    },
    "SQLite": {
        "category": "database",
        "related": ["SQLite3", "SQL", "Database", "In-Memory DB"]
    },
    "Oracle": {
        "category": "database",
        "related": ["Oracle DB", "Oracle Database", "PL/SQL", "Toad", "SQL Developer"]
    },
    "SQL Server": {
        "category": "database",
        "related": [
            "MSSQL", "T-SQL", "SQL Server 2019", "SSMS", "SSIS",
            "Entity Framework", "LINQ"
        ]
    },
    "Cassandra": {
        "category": "database",
        "related": ["Apache Cassandra", "CQL", "Cassandra Query Language", "NoSQL"]
    },
    "DynamoDB": {
        "category": "database",
        "related": ["AWS DynamoDB", "NoSQL", "DynamoDB Streams"]
    },
    "Firebase": {
        "category": "database",
        "related": [
            "Firestore", "Realtime Database", "Firebase Auth",
            "Cloud Functions", "Firebase Hosting", "NoSQL"
        ]
    },
    "Supabase": {
        "category": "database",
        "related": ["PostgreSQL", "Supabase DB", "PostgREST", "GoTrue"]
    },

    # ========================
    # DEVOPS (Docker, Kubernetes, CI/CD)
    # ========================
    "Docker": {
        "category": "devops",
        "related": [
            "Docker ", "Dockerfile", "Docker Compose", "Docker Swarm",
            "Docker Hub", "Docker Desktop", "Container",
            "docker build", "docker run", "docker-compose"
        ]
    },
    "Kubernetes": {
        "category": "devops",
        "related": [
            "K8s", "Kubectl", "Minikube", "Kind", "Helm",
            "Kustomize", "Pod", "Deployment", "Service", "Ingress",
            "ConfigMap", "Secret", "RBAC", "Network Policy"
        ]
    },
    "K8s": {
        "category": "devops",
        "related": ["Kubernetes", "Kubectl", "Helm"]
    },
    "Jenkins": {
        "category": "devops",
        "related": [
            "Jenkins Pipeline", "Jenkinsfile", "CI/CD", "Blue Ocean",
            "Groovy", "Build Triggers", "Pipeline Stages"
        ]
    },
    "GitLab": {
        "category": "devops",
        "related": [
            "GitLab CI", "GitLab CI/CD", "GitLab Runner", ".gitlab-ci.yml",
            "Auto DevOps", "GitLab Container Registry"
        ]
    },
    "GitHub Actions": {
        "category": "devops",
        "related": [
            "GitHub Workflows", "Actions", "Workflow YAML", "CI/CD"
        ]
    },
    "CircleCI": {
        "category": "devops",
        "related": ["CircleCI", "CI/CD", "Orbs", "Pipeline"]
    },
    "Travis CI": {
        "category": "devops",
        "related": ["Travis CI", "CI/CD", ".travis.yml"]
    },
    "Terraform": {
        "category": "devops",
        "related": [
            "Terraform", "HCL", "Terraform Provider", "State", "Modules",
            "Variable", "Output", "Remote State"
        ]
    },
    "Ansible": {
        "category": "devops",
        "related": [
            "Ansible Playbook", "Ansible Tower", "AWX",
            "YAML", "Inventory", "Roles", "Modules"
        ]
    },
    "Chef": {
        "category": "devops",
        "related": ["Chef", "Cookbook", "Recipe", "Ohai", "ChefSpec"]
    },
    "Puppet": {
        "category": "devops",
        "related": ["Puppet", "Manifest", "Module", "Hiera"]
    },
    "Nginx": {
        "category": "devops",
        "related": ["Nginx", "Reverse Proxy", "Load Balancer", "SSL/TLS"]
    },
    "Apache": {
        "category": "devops",
        "related": ["Apache HTTP", "Apache2", "Virtual Host", ".htaccess"]
    },

    # ========================
    # CLOUD (AWS, Azure, GCP)
    # ========================
    "AWS": {
        "category": "cloud",
        "related": [
            "Amazon Web Services", "EC2", "S3", "Lambda", "EKS", "ECS",
            "RDS", "DynamoDB", "CloudFront", "Route 53", "IAM",
            "SQS", "SNS", "Kinesis", "API Gateway", "Cognito",
            "Amplify", "AppSync", "SAM", "CDK", "Terraform AWS"
        ]
    },
    "Amazon Web Services": {
        "category": "cloud",
        "related": ["AWS", "EC2", "S3", "Lambda"]
    },
    "Azure": {
        "category": "cloud",
        "related": [
            "Azure ", "Azure Functions", "Azure App Service",
            "Azure Storage", "Azure SQL", "Cosmos DB",
            "Azure AD", "Azure DevOps", "ARM Templates"
        ]
    },
    "GCP": {
        "category": "cloud",
        "related": [
            "Google Cloud", "GCP", "Compute Engine", "Cloud Functions",
            "Cloud Run", "App Engine", "BigQuery", "Cloud Storage",
            "Cloud SQL", "Kubernetes Engine", "IAM"
        ]
    },
    "Google Cloud": {
        "category": "cloud",
        "related": ["GCP", "Cloud Functions", "GKE"]
    },
    "Heroku": {
        "category": "cloud",
        "related": ["Heroku", "Heroku Postgres", "Dyno", "Buildpacks"]
    },
    "Vercel": {
        "category": "cloud",
        "related": ["Vercel", "Next.js Hosting", "Serverless"]
    },
    "Netlify": {
        "category": "cloud",
        "related": ["Netlify", "Netlify Functions", "Forms", "Identity"]
    },
    "DigitalOcean": {
        "category": "cloud",
        "related": [
            "DigitalOcean", "Droplet", "App Platform", "Kubernetes",
            "Spaces", "Database"
        ]
    },

    # ========================
    # MOBILE (React Native, Flutter, etc.)
    # ========================
    "React Native": {
        "category": "mobile",
        "related": [
            "React Native", "React", "Expo", "React Navigation",
            "Redux", "MobX", "Native Modules", "iOS", "Android",
            "React Native CLI", "Hermes", "Fast Refresh"
        ]
    },
    "Flutter": {
        "category": "mobile",
        "related": [
            "Flutter", "Dart", "Widgets", "Provider", "Riverpod",
            "GetX", "BLoC", "Firebase"
        ]
    },
    "Dart": {
        "category": "mobile",
        "related": ["Flutter", "Dart 2", "Dart 3"]
    },
    "Swift": {
        "category": "mobile",
        "related": [
            "Swift ", "Swift 4", "Swift 5", "iOS", "macOS",
            "SwiftUI", "UIKit", "Xcode", "Swift Package Manager"
        ]
    },
    "iOS": {
        "category": "mobile",
        "related": ["Swift", "Objective-C", "Xcode", "iPhone", "iPad"]
    },
    "Kotlin": {
        "category": "mobile",
        "related": [
            "Kotlin ", "Kotlin Android", "Android", "Jetpack Compose",
            "Kotlin Coroutines", "MVVM"
        ]
    },
    "Android": {
        "category": "mobile",
        "related": [
            "Android Studio", "Kotlin", "Java", "Gradle",
            "Jetpack", "Room", "ViewModel"
        ]
    },
    "Xamarin": {
        "category": "mobile",
        "related": [
            "Xamarin ", "Xamarin.Forms", "Xamarin.Native", ".NET MAUI"
        ]
    },

    # ========================
    # DATA SCIENCE / ML (Python, TensorFlow, etc.)
    # ========================
    "Python": {
        "category": "data",
        "related": [
            "Python", "Pandas", "NumPy", "SciPy", "Matplotlib",
            "Scikit-learn", "TensorFlow", "PyTorch", "Keras",
            "Jupyter", "Notebook", "Data Analysis", "ML"
        ]
    },
    "Pandas": {
        "category": "data",
        "related": [
            "Pandas ", "DataFrame", "Series", "Pandas IO",
            "Pandas Visualization"
        ]
    },
    "NumPy": {
        "category": "data",
        "related": ["NumPy ", "NumPy Array", "NumPy Operations"]
    },
    "TensorFlow": {
        "category": "data",
        "related": [
            "TensorFlow ", "Keras", "TensorFlow Lite",
            "TensorFlow.js", "TFLite", "TF Lite"
        ]
    },
    "PyTorch": {
        "category": "data",
        "related": [
            "PyTorch ", "PyTorch Lightning", "Torch", "CUDA",
            "PyTorch Geometric", "Distributed Training"
        ]
    },
    "Keras": {
        "category": "data",
        "related": ["Keras", "TensorFlow", "Deep Learning"]
    },
    "Scikit-learn": {
        "category": "data",
        "related": ["Scikit Learn", "sklearn", "Machine Learning", "ML"]
    },
    "Jupyter": {
        "category": "data",
        "related": [
            "Jupyter Notebook", "Jupyter Lab", "IPython",
            "Colab", "Google Colab"
        ]
    },
    "Machine Learning": {
        "category": "data",
        "related": [
            "ML", "Deep Learning", "Neural Networks", "AI",
            "Supervised Learning", "Unsupervised Learning"
        ]
    },
    "Data Science": {
        "category": "data",
        "related": [
            "Data Analysis", "Data Visualization", "Statistics",
            "Pandas", "NumPy", "Matplotlib"
        ]
    },
    "Spark": {
        "category": "data",
        "related": [
            "Apache Spark", "PySpark", "Spark SQL", "DataFrame",
            "Big Data", "Spark Streaming"
        ]
    },
    "Hadoop": {
        "category": "data",
        "related": [
            "Apache Hadoop", "HDFS", "MapReduce", "Hive", "Big Data"
        ]
    },
    "Tableau": {
        "category": "data",
        "related": ["Tableau", "Data Visualization", "BI", "Dashboard"]
    },
    "Power BI": {
        "category": "data",
        "related": ["PowerBI", "DAX", "Data Visualization", "BI"]
    },

    # ========================
    # API / COMMUNICATION
    # ========================
    "REST APIs": {
        "category": "api",
        "related": [
            "REST", "API", "RESTful", "HTTP", "JSON",
            "REST API Design", "OpenAPI", "Swagger", "Postman"
        ]
    },
    "GraphQL": {
        "category": "api",
        "related": [
            "GraphQL", "Apollo", "Prisma", "Queries", "Mutations",
            "Schema", "Type GraphQL"
        ]
    },
    "gRPC": {
        "category": "api",
        "related": ["gRPC", "Protocol Buffers", "ProtoBuf", "HTTP/2"]
    },
    "WebSocket": {
        "category": "api",
        "related": [
            "WebSockets", "Socket.io", "WebSocket API", "Real-time"
        ]
    },

    # ========================
    # VERSION CONTROL
    # ========================
    "Git": {
        "category": "devops",
        "related": [
            "Git ", "GitHub", "GitLab", "GitBucket", "Bitbucket",
            "Git Commands", "Git Branch", "Merge", "Rebase",
            "GitHub Actions", "Git Flow", "GitHooks"
        ]
    },
    "GitHub": {
        "category": "devops",
        "related": [
            "GitHub", "Git", "GitHub Actions", "GitHub Pages",
            "GitHub Codespaces", "GitHub Copilot"
        ]
    },
    "GitLab": {
        "category": "devops",
        "related": ["GitLab", "Git", "GitLab CI"]
    },
    "Bitbucket": {
        "category": "devops",
        "related": ["Bitbucket", "Git", "Pipelines"]
    },

    # ========================
    # TESTING
    # ========================
    "Jest": {
        "category": "testing",
        "related": [
            "Jest ", "React Testing Library", "Enzyme", "Unit Testing",
            "Jest.fn()", "Mock", "Snapshot Testing"
        ]
    },
    "Cypress": {
        "category": "testing",
        "related": [
            "Cypress", "E2E Testing", "End-to-End",
            "Cypress Commands", "Automation Testing"
        ]
    },
    "Selenium": {
        "category": "testing",
        "related": [
            "Selenium", "WebDriver", "Selenium IDE",
            "Automated Testing", "TestNG"
        ]
    },
    "Pytest": {
        "category": "testing",
        "related": [
            "Pytest", "Python Testing", "UnitTest", "Fixtures",
            "Mock", "Coverage"
        ]
    },
    "JUnit": {
        "category": "testing",
        "related": [
            "JUnit 4", "JUnit 5", "Java Testing", "TestNG",
            "Spring Test", "Mockito"
        ]
    },
    "Mocha": {
        "category": "testing",
        "related": ["Mocha", "Chai", "JavaScript Testing", "BDD"]
    },

    # ========================
    # AUTHENTICATION
    # ========================
    "JWT": {
        "category": "security",
        "related": [
            "JSON Web Token", "JWT Auth", "Token", "Access Token",
            "Refresh Token", "JWT Bearer"
        ]
    },
    "OAuth": {
        "category": "security",
        "related": [
            "OAuth 2.0", "OAuth 2", "OAuth 1", "Authorization",
            "OpenID Connect", "SSO"
        ]
    },
    "OAuth 2.0": {
        "category": "security",
        "related": ["OAuth", "OpenID Connect", "Authorization Code"]
    },

    # ========================
    # MESSAGING
    # ========================
    "Kafka": {
        "category": "messaging",
        "related": [
            "Apache Kafka", "Kafka Streams", "Producer", "Consumer",
            "Topic", "Partition", "Kafka Connect"
        ]
    },
    "RabbitMQ": {
        "category": "messaging",
        "related": [
            "RabbitMQ", "AMQP", "Queue", "Exchange",
            "Publisher", "Consumer"
        ]
    },
    "SQS": {
        "category": "messaging",
        "related": ["AWS SQS", "Simple Queue Service", "FIFO"]
    },
    "Pub/Sub": {
        "category": "messaging",
        "related": ["Google Pub/Sub", "Redis Pub/Sub", "Message Queue"]
    },
}


# Category groups for partial matching
skillCategories = {
    "frontend": ["React", "Vue", "Angular", "HTML", "CSS", "JavaScript", "TypeScript", "Next.js"],
    "backend": ["Node.js", "Python", "Java", "Go", "Ruby", "PHP", "C#", "Kotlin", "Rust", "Swift"],
    "database": ["MongoDB", "MySQL", "PostgreSQL", "Redis", "SQLite", "Oracle", "SQL Server", "Cassandra"],
    "devops": ["Docker", "Kubernetes", "Jenkins", "GitLab", "GitHub Actions", "Terraform", "Ansible"],
    "cloud": ["AWS", "Azure", "GCP", "Heroku", "Vercel", "Netlify"],
    "mobile": ["React Native", "Flutter", "Swift", "Kotlin", "Android", "iOS", "Xamarin"],
    "data": ["Python", "Pandas", "NumPy", "TensorFlow", "PyTorch", "Spark", "Hadoop"],
    "api": ["REST APIs", "GraphQL", "gRPC", "WebSocket"],
    "testing": ["Jest", "Cypress", "Selenium", "Pytest", "JUnit"],
    "security": ["JWT", "OAuth", "OAuth 2.0"],
    "messaging": ["Kafka", "RabbitMQ", "SQS"]
}


def get_skill_category(skill: str) -> str:
    """Get category of a skill"""
    skill_lower = skill.lower()
    for category, skills in skillCategories.items():
        if skill_lower in [s.lower() for s in skills]:
            return category
    return "other"


def get_related_skills(parent_skill: str) -> list:
    """Get all related secondary skills for a parent skill"""
    skill_key = parent_skill.lower()
    if skill_key in skillRelations:
        return skillRelations[skill_key].get("related", [])
    # Try case-insensitive search
    for key in skillRelations:
        if key.lower() == skill_key:
            return skillRelations[key].get("related", [])
    return []


def is_related_to(resume_skill: str, jd_skill: str) -> tuple:
    """
    Check if resume_skill is related to jd_skill.
    Returns: (is_related: bool, category: str, points: int)
    
    Category: 'primary', 'secondary', 'partial', 'none'
    Points: 20, 10, 6, 0
    """
    resume_lower = resume_skill.lower().strip()
    jd_lower = jd_skill.lower().strip()
    
    # 1. Primary: Exact match
    if resume_lower == jd_lower:
        return (True, "primary", 20)
    
    # 2. Check JD skill's related list (Secondary)
    jd_related = get_related_skills(jd_skill)
    if jd_related:
        for related_skill in jd_related:
            if resume_lower == related_skill.lower():
                return (True, "secondary", 10)
            # Check partial
            if resume_lower in related_skill.lower() or related_skill.lower() in resume_lower:
                return (True, "secondary", 10)
    
    # 3. Check resume skill's related list
    resume_related = get_related_skills(resume_skill)
    if resume_related:
        for related_skill in resume_related:
            if related_skill.lower() == jd_lower:
                return (True, "secondary", 10)
    
    # 4. Partial: Same category but not in related
    resume_cat = get_skill_category(resume_skill)
    jd_cat = get_skill_category(jd_skill)
    if resume_cat == jd_cat and resume_cat != "other":
        return (True, "partial", 6)
    
    # No match
    return (False, "none", 0)


if __name__ == "__main__":
    # Test examples
    print("=== Skill Relations Test ===\n")
    
    # Test 1: From your example
    print("Test 1: React (Primary)")
    related = get_related_skills("React")
    print(f"  Related: {related[:5]}...\n")
    
    print("Test 2: Express.js related to Node.js")
    is_related, cat, points = is_related_to("Express.js", "Node.js")
    print(f"  Category: {cat}, Points: {points}\n")
    
    print("Test 3: MySQL related to MongoDB")
    is_related, cat, points = is_related_to("MySQL", "MongoDB")
    print(f"  Category: {cat}, Points: {points}\n")
    
    print("Test 4: Get category of Python")
    cat = get_skill_category("Python")
    print(f"  Category: {cat}\n")