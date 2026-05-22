from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from redis_om import HashModel, NotFoundError
import httpx
import asyncio
from database import redis

app = FastAPI(title="Order Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:3000'],
    allow_methods=['*'],
    allow_headers=['*']
)

class Order(HashModel, index=True):
    product_id: str
    price: float
    fee: float
    total: float
    quantity: int
    status: str 

    class Meta:
        database = redis

@app.get('/orders/{pk}')
async def get_order(pk: str):
    try:
        return Order.get(pk)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Order not found")

@app.post('/orders')
async def create_order(body: dict, background_tasks: BackgroundTasks):
    if "id" not in body or "quantity" not in body:
        raise HTTPException(status_code=422, detail="Missing required fields: id, quantity")

    async with httpx.AsyncClient() as client:
        response = await client.get(f'http://localhost:8000/products/{body["id"]}')
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Product not found in Inventory")
        product = response.json()

    order = Order(
        product_id=body['id'],
        price=product['price'],
        fee=0.2 * product['price'],
        total=1.2 * product['price'] * body['quantity'],
        quantity=body['quantity'],
        status='pending'
    )
    order.save()

    background_tasks.add_task(process_order, order)

    return order

async def process_order(order: Order):
    await asyncio.sleep(5) 
    order.status = 'completed'
    order.save()
    redis.xadd('order_completed', order.model_dump(), '*')