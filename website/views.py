from flask import Blueprint, render_template, flash, redirect, request, jsonify
from .models import Product, Cart, Order, Wishlist
from flask_login import login_required, current_user
from . import db
from intasend import APIService


views = Blueprint('views', __name__)

API_PUBLISHABLE_KEY = 'ISPubKey_live_1577ccf6-881c-4711-a6a5-f0699797b0e5'

API_TOKEN = 'ISSecretKey_live_82f96a3d-ae45-4c7d-b162-c3edb20f87c0'


@views.route('/')
def home():

    items = Product.query.filter_by(flash_sale=True)

    return render_template('home.html', items=items, cart=Cart.query.filter_by(customer_link=current_user.id).all()
                           if current_user.is_authenticated else [])


@views.route('/products')
def products():
    # Get filter parameters from the request
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    category_id = request.args.get('category_id', type=int)
    flash_sale = request.args.get('flash_sale', type=bool)

    # Start with a base query
    query = Product.query

    # Apply filters based on request parameters
    if min_price is not None:
        query = query.filter(Product.current_price >= min_price)
    if max_price is not None:
        query = query.filter(Product.current_price <= max_price)
    if category_id is not None:
        query = query.filter_by(category_id=category_id)
    if flash_sale is not None:
        query = query.filter_by(flash_sale=flash_sale)
    else:
        # Exclude flash_sale items by default if no filter is applied
        query = query.filter_by(flash_sale=False)

    # Fetch filtered products
    filtered_products = query.all()

    return render_template('products.html', products=filtered_products)

@views.route('/product-section')
def product_section():
    # Get the maximum price from the request (default to None if not provided)
    max_price = request.args.get('max_price', type=float)

    # Fetch the maximum price from the database to set the slider's max value
    max_product_price = db.session.query(db.func.max(Product.current_price)).scalar() or 10000

    # Start with a base query excluding flash_sale items
    query = Product.query.filter_by(flash_sale=False)

    # Apply price filter if max_price is provided
    if max_price is not None:
        query = query.filter(Product.current_price <= max_price)

    # Fetch filtered products
    items = query.all()

    return render_template('product_section.html', items=items, max_price=max_product_price)

@views.route('/add-to-cart/<int:item_id>')
@login_required
def add_to_cart(item_id):
    item_to_add = Product.query.get(item_id)
    item_exists = Cart.query.filter_by(
        product_link=item_id, customer_link=current_user.id).first()
    if item_exists:
        try:
            item_exists.quantity = item_exists.quantity + 1
            db.session.commit()
            flash(
                f' Quantity of { item_exists.product.product_name } has been updated')
            return redirect(request.referrer)
        except Exception as e:
            print('Quantity not Updated', e)
            flash(
                f'Quantity of { item_exists.product.product_name } not updated')
            return redirect(request.referrer)

    new_cart_item = Cart()
    new_cart_item.quantity = 1
    new_cart_item.product_link = item_to_add.id
    new_cart_item.customer_link = current_user.id

    try:
        db.session.add(new_cart_item)
        db.session.commit()
        flash(f'{new_cart_item.product.product_name} added to cart')
    except Exception as e:
        print('Item not added to cart', e)
        flash(f'{new_cart_item.product.product_name} has not been added to cart')

    return redirect(request.referrer)


@views.route('/cart')
@login_required
def show_cart():
    cart = Cart.query.filter_by(customer_link=current_user.id).all()
    amount = 0
    for item in cart:
        amount += item.product.current_price * item.quantity

    return render_template('cart.html', cart=cart, amount=amount, total=amount+200)


@views.route('/pluscart')
@login_required
def plus_cart():
    if request.method == 'GET':
        cart_id = request.args.get('cart_id')
        cart_item = Cart.query.get(cart_id)
        cart_item.quantity = cart_item.quantity + 1
        db.session.commit()

        cart = Cart.query.filter_by(customer_link=current_user.id).all()

        amount = 0

        for item in cart:
            amount += item.product.current_price * item.quantity

        data = {
            'quantity': cart_item.quantity,
            'amount': amount,
            'total': amount + 200
        }

        return jsonify(data)


@views.route('/minuscart')
@login_required
def minus_cart():
    if request.method == 'GET':
        cart_id = request.args.get('cart_id')
        cart_item = Cart.query.get(cart_id)
        cart_item.quantity = cart_item.quantity - 1
        db.session.commit()

        cart = Cart.query.filter_by(customer_link=current_user.id).all()

        amount = 0

        for item in cart:
            amount += item.product.current_price * item.quantity

        data = {
            'quantity': cart_item.quantity,
            'amount': amount,
            'total': amount + 200
        }

        return jsonify(data)


@views.route('removecart')
@login_required
def remove_cart():
    if request.method == 'GET':
        cart_id = request.args.get('cart_id')
        cart_item = Cart.query.get(cart_id)
        db.session.delete(cart_item)
        db.session.commit()

        cart = Cart.query.filter_by(customer_link=current_user.id).all()

        amount = 0

        for item in cart:
            amount += item.product.current_price * item.quantity

        data = {
            'quantity': cart_item.quantity,
            'amount': amount,
            'total': amount + 200
        }

        return jsonify(data)


@views.route('/place-order')
@login_required
def place_order():
    customer_cart = Cart.query.filter_by(customer_link=current_user.id)
    if customer_cart:
        try:
            total = 0
            for item in customer_cart:
                total += item.product.current_price * item.quantity

            service = APIService(
                token=API_TOKEN, publishable_key=API_PUBLISHABLE_KEY, test=True)
            create_order_response = service.collect.mpesa_stk_push(phone_number='YOUR_NUMBER ', email=current_user.email,
                                                                   amount=total + 200, narrative='Purchase of goods')

            for item in customer_cart:
                new_order = Order()
                new_order.quantity = item.quantity
                new_order.price = item.product.current_price
                new_order.status = create_order_response['invoice']['state'].capitalize(
                )
                new_order.payment_id = create_order_response['id']

                new_order.product_link = item.product_link
                new_order.customer_link = item.customer_link

                db.session.add(new_order)

                product = Product.query.get(item.product_link)

                product.in_stock -= item.quantity

                db.session.delete(item)

                db.session.commit()

            flash('Order Placed Successfully')

            return redirect('/orders')
        except Exception as e:
            print(e)
            flash('Order not placed')
            return redirect('/')
    else:
        flash('Your cart is Empty')
        return redirect('/')

 
@views.route('/orders')
@login_required
def order():
    orders = Order.query.filter_by(customer_link=current_user.id).all()
    return render_template('orders.html', orders=orders)


@views.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        search_query = request.form.get('search')
        items = Product.query.filter(
            Product.product_name.ilike(f'%{search_query}%')).all()
        return render_template('search.html', items=items, cart=Cart.query.filter_by(customer_link=current_user.id).all()
                               if current_user.is_authenticated else [])


@views.route('/add-to-wishlist/<int:item_id>')
@login_required
def add_to_wishlist(item_id):
    item_to_add = Product.query.get(item_id)
    item_exists = Wishlist.query.filter_by(
        product_link=item_id, customer_link=current_user.id).first()
    
    if item_exists:
        flash(f'{item_to_add.product_name} is already in your wishlist')
        return redirect(request.referrer)

    new_wishlist_item = Wishlist()
    new_wishlist_item.product_link = item_to_add.id
    new_wishlist_item.customer_link = current_user.id

    try:
        db.session.add(new_wishlist_item)
        db.session.commit()
        flash(f'{item_to_add.product_name} added to wishlist')
    except Exception as e:
        print('Item not added to wishlist', e)
        flash(f'{item_to_add.product_name} has not been added to wishlist')

    return redirect(request.referrer)

@views.route('/wishlist')
@login_required
def wishlist():
    wishlist_items = Wishlist.query.filter_by(customer_link=current_user.id).all()
    return render_template('wishlist.html', wishlist_items=wishlist_items)

@views.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


@views.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

    return render_template('search.html')
