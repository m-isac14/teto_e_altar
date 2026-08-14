from database import SessionLocal, engine
import models
from auth import get_password_hash

def seed_db():
    print("Iniciando seed do banco de dados...")
    db = SessionLocal()

    try:
        # Verifica se já existem usuários para não duplicar
        if db.query(models.User).first():
            print("Banco de dados já populado!")
            return

        # 1. Cria Usuários
        user1 = models.User(nome="Isac", email="isac@teto.com", senha_hash=get_password_hash("123456"))
        user2 = models.User(nome="Noiva", email="noiva@teto.com", senha_hash=get_password_hash("123456"))
        db.add(user1)
        db.add(user2)
        
        # 2. Cria Metas
        goal1 = models.Goal(nome="Casamento", valor_objetivo=50000.0)
        goal2 = models.Goal(nome="Apartamento", valor_objetivo=150000.0)
        db.add(goal1)
        db.add(goal2)
        db.commit() # Commita metas para obter os IDs

        # 3. Cria Categorias
        categorias = [
            # Categorias Gerais
            models.Category(nome="Buffet", goal_id=goal1.id),
            models.Category(nome="Documentação", goal_id=None), # Nao associada rigidamente ou pode associar ao AP/Casamento
            models.Category(nome="Móveis", goal_id=goal2.id),
            models.Category(nome="Material de Construção", goal_id=goal2.id),
            models.Category(nome="Gerais", goal_id=None)
        ]
        
        db.add_all(categorias)
        db.commit()
        
        print("Seed finalizado com sucesso! Usuários criados: isac@teto.com e noiva@teto.com | Senha: 123456")

    except Exception as e:
        print(f"Erro ao popular banco de dados: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    models.Base.metadata.create_all(bind=engine)
    seed_db()
