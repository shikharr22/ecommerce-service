-- USERS 
CREATE TABLE IF NOT EXISTS users(
    id BIGSERIAL PRIMARY KEY,  -- 64 bit auto incrementing integer maintaine by postgres
    email TEXT NOT NULL UNIQUE,
    hashed_password TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now() -- iternally created_at will be stored in UTC  , but when queired it will return the local time
);

-- CATEGORIES
CREATE TABLE IF NOT EXISTS categories(
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- PRODUCTS
CREATE TABLE IF NOT EXISTS products(
    id BIGSERIAL PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    category_id BIGINT REFERENCES categories(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- PRODUCT VARIANTS
CREATE TABLE IF NOT EXISTS product_variants(
    id BIGSERIAL PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE,
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    price_cents BIGINT NOT NULL CHECK (price_cents>=0),
    attributes JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- INDEXES ON PRODUCT VARIANTS
CREATE INDEX IF NOT EXISTS idx_variant_product_id ON product_variants(product_id);
CREATE INDEX IF NOT EXISTS idx_variant_attributes_gin ON product_variants USING gin (attributes); --GIN(Generalised inverted index)

-- INVENTORY
CREATE TABLE IF NOT EXISTS inventory(
    variant_id BIGINT PRIMARY KEY REFERENCES product_variants(id) ON DELETE CASCADE,
    available INT NOT NULL DEFAULT 0 CHECK (available>=0),
    reserved INT NOT NULL DEFAULT 0 CHECK (reserved>=0),
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ADDRESSES
CREATE TABLE IF NOT EXISTS addresses (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
  line1 TEXT,
  line2 TEXT,
  city TEXT,
  region TEXT,
  country TEXT,
  postal_code TEXT
);

-- ORDERS
CREATE TABLE IF NOT EXISTS orders(
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id),
    status TEXT NOT NULL CHECK (status IN ('shipped','created','paid','refunded','cancelled' )),
    total_cents BIGINT NOT NULL CHECK (total_cents>=0),
    currency TEXT NOT NULL DEFAULT 'USD',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    billing_address_id BIGINT REFERENCES addresses(id),
    shipping_address_id BIGINT REFERENCES addresses(id),
    payment_provider_id TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- INDEX ON ORDERS
CREATE INDEX IF NOT EXISTS idx_orders_user_created_at ON orders(user_id,created_at DESC);

-- ORDER ITEMS
CREATE TABLE IF NOT EXISTS order_items(
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    variant_id BIGINT NOT NULL REFERENCES product_variants(id),
    unit_price_cents BIGINT NOT NULL CHECK (unit_price_cents>=0),
    quantity INT NOT NULL CHECK (quantity > 0),
    subtotal_cents BIGINT NOT NULL CHECK (subtotal_cents>=0)
);

-- INDEXES ON ORDER ITEMS
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_variant_id ON order_items(variant_id);

-- CART
CREATE TABLE IF NOT EXISTS carts(
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- CART ITEMS
CREATE TABLE IF NOT EXISTS cart_items(
    id BIGSERIAL PRIMARY KEY,
    cart_id BIGINT NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
    variant_id BIGINT NOT NULL REFERENCES product_variants(id),
    quantity INT NOT NULL CHECK (quantity >0) 
);

-- INDEX ON cart items
CREATE INDEX IF NOT EXISTS idx_cart_items_cart_id  ON cart_items(cart_id);