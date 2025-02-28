from flask import Blueprint, render_template, flash, redirect, request, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from .models import Product, Order, Customer, Cart
from . import db
from .forms import ShopItemsForm, OrderForm


admin = Blueprint('admin', __name__)


@admin.route('/media/<path:filename>')
def get_image(filename):
    return send_from_directory('../media', filename)


@admin.route('/add-shop-items', methods=['GET', 'POST'])
@login_required
def add_shop_items():
    if current_user.id != 1:
        return render_template('404.html'), 403

    form = ShopItemsForm()
    if form.validate_on_submit():
        product_name = form.product_name.data
        current_price = form.current_price.data
        previous_price = form.previous_price.data
        in_stock = form.in_stock.data
        flash_sale = form.flash_sale.data

        file = form.product_picture.data

        file_name = secure_filename(file.filename)

        file_path = f'./media/{file_name}'

        file.save(file_path)

        new_product = Product(
            product_name=product_name,
            current_price=current_price,
            previous_price=previous_price,
            in_stock=in_stock,
            flash_sale=flash_sale,
            product_picture=file_path
        )

        try:
            db.session.add(new_product)
            db.session.commit()
            flash(f'{product_name} added successfully!', 'success')
            return redirect('/shop-items')
        except Exception as e:
            db.session.rollback()
            print(f"Error: {e}")
            flash('Failed to add product. Please try again.', 'danger')

    return render_template('add_shop_items.html', form=form)


@admin.route('/shop-items')
@login_required
def shop_items():
    if current_user.id != 1:
        return render_template('404.html'), 403

    items = Product.query.order_by(Product.date_added).all()
    return render_template('shop_items.html', items=items)


@admin.route('/update-item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def update_item(item_id):
    if current_user.id != 1:
        return render_template('404.html'), 403

    item_to_update = Product.query.get_or_404(item_id)
    form = ShopItemsForm(obj=item_to_update)

    if form.validate_on_submit():
        form.populate_obj(item_to_update)
        file = form.product_picture.data

        if file:
            file_name = secure_filename(file.filename)
            file_path = f'./media/{file_name}'
            file.save(file_path)
            item_to_update.product_picture = file_path

        try:
            db.session.commit()
            flash(f'{item_to_update.product_name} updated successfully!', 'success')
            return redirect('/shop-items')
        except Exception as e:
            db.session.rollback()
            print(f"Error: {e}")
            flash('Failed to update product. Please try again.', 'danger')

    return render_template('update_item.html', form=form, item=item_to_update)


@admin.route('/delete-item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def delete_item(item_id):
    if current_user.id == 1:
        try:
            # Find the product to delete
            item_to_delete = Product.query.get_or_404(item_id)

            # Delete all related rows in the cart table
            Cart.query.filter_by(product_link=item_id).delete()

            # Delete the product
            db.session.delete(item_to_delete)
            db.session.commit()
            flash('Product and related cart items deleted successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"Error: {e}")
            flash(f'Failed to delete product. Error: {e}', 'danger')
        return redirect('/shop-items')
    return render_template('404.html'), 403

@admin.route('/view-orders')
@login_required
def order_view():
    if current_user.id != 1:
        return render_template('404.html'), 403

    orders = Order.query.all()
    return render_template('view_orders.html', orders=orders)


@admin.route('/update-order/<int:order_id>', methods=['GET', 'POST'])
@login_required
def update_order(order_id):
    if current_user.id != 1:
        return render_template('404.html'), 403

    order = Order.query.get_or_404(order_id)
    form = OrderForm(obj=order)

    if form.validate_on_submit():
        form.populate_obj(order)
        try:
            db.session.commit()
            flash(f'Order {order_id} updated successfully!', 'success')
            return redirect('/view-orders')
        except Exception as e:
            db.session.rollback()
            print(f"Error: {e}")
            flash('Failed to update order. Please try again.', 'danger')

    return render_template('order_update.html', form=form, order=order)


@admin.route('/customers')
@login_required
def display_customers():
    if current_user.id != 1:
        return render_template('404.html'), 403

    customers = Customer.query.all()
    return render_template('customers.html', customers=customers)


@admin.route('/admin-page')
@login_required
def admin_page():
    if current_user.id != 1:
        return render_template('404.html'), 403

    return render_template('admin.html')
