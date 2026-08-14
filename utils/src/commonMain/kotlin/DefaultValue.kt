package config.structs

interface DefaultValue<T> {
    fun defaultInstance(): T
}
