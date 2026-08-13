package com.galaxia5987.app

import com.galaxia5987.NativeLibrary

fun main() {
    NativeLibrary().use {
        println(it.add(200,2))
    }
}