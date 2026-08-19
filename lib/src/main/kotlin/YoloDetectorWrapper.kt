package com.galaxia5987.lib

import org.bytedeco.javacpp.Loader
import org.bytedeco.javacpp.Pointer
import org.bytedeco.javacpp.annotation.*
import org.bytedeco.opencv.opencv_core.Mat

data class BoundingBox(val x: Int, val y: Int, val width: Int, val height: Int)

@Platform(
    include = ["inference/YoloDetector.hpp"],
    link = ["aether-vision-lib", "opencv_core"]
)
@Name("BoundingBox")
@Namespace("aethervision")
class NativeBoundingBox : Pointer {
    companion object {
        init {
            Loader.load(NativeBoundingBox::class.java)
        }
    }

    constructor() { allocate() }
    constructor(p: Pointer) : super(p)

    external fun allocate()

    @MemberGetter external fun x(): Int
    @MemberSetter external fun x(x: Int): NativeBoundingBox

    @MemberGetter external fun y(): Int
    @MemberSetter external fun y(y: Int): NativeBoundingBox

    @MemberGetter external fun width(): Int
    @MemberSetter external fun width(width: Int): NativeBoundingBox

    @MemberGetter external fun height(): Int
    @MemberSetter external fun height(height: Int): NativeBoundingBox

    fun toJvm(): BoundingBox = BoundingBox(
        x = x(),
        y = y(),
        width = width(),
        height = height()
    )
}

data class Detection(val box: BoundingBox, val confidence: Float, val classId: Int)

@Platform(
    include = ["inference/YoloDetector.hpp"],
    link = ["aether-vision-lib", "opencv_core"]
)
@Name("Detection")
@Namespace("aethervision")
class NativeDetection : Pointer {
    companion object {
        init {
            Loader.load(NativeDetection::class.java)
        }
    }

    constructor() { allocate() }
    constructor(p: Pointer) : super(p)

    external fun allocate()

    @ByRef @MemberGetter external fun box(): NativeBoundingBox
    @MemberSetter external fun box(@Const @ByRef box: NativeBoundingBox): NativeDetection

    @MemberGetter external fun confidence(): Float
    @MemberSetter external fun confidence(confidence: Float): NativeDetection

    @MemberGetter external fun class_id(): Int
    @MemberSetter external fun class_id(class_id: Int): NativeDetection

    fun toJvm() = Detection(
        box = box().toJvm(),
        confidence = confidence(),
        classId = class_id()
    )
}

@Platform(
    include = ["inference/YoloDetector.hpp"],
    link = ["aether-vision-lib", "opencv_core"]
)
@Name("std::vector<aethervision::Detection>")
class DetectionVector : Pointer {
    companion object {
        init {
            Loader.load(DetectionVector::class.java)
        }
    }

    constructor() { allocate() }
    constructor(n: Long) { allocate(n) }
    constructor(p: Pointer) : super(p)

    external fun allocate()
    external fun allocate(n: Long)

    @Name("operator=")
    @ByRef external fun put(@Const @ByRef x: DetectionVector): DetectionVector

    @Index(function = "at")
    @ByRef external fun get(i: Long): NativeDetection

    external fun size(): Long
    external fun push_back(@Const @ByRef value: NativeDetection)
    external fun clear()

    fun toList(): List<Detection> {
        val list = ArrayList<Detection>(size().toInt())
        for (i in 0 until size()) {
            list += get(i).toJvm()
        }
        return list
    }
}

@Platform(
    include = ["inference/YoloDetector.hpp"],
    link = ["aether-vision-lib", "opencv_core"]
)
@Name("YoloDetector")
@Namespace("aethervision")
class YoloDetector : Pointer {
    companion object {
        init {
            Loader.load(YoloDetector::class.java)
        }
    }

    constructor(modelPath: String, useCUDA: Boolean) {
        allocate(modelPath, useCUDA)
    }

    constructor(p: Pointer) : super(p)

    protected external fun allocate(
        @Const @ByRef @StdString modelPath: String,
        useCUDA: Boolean
    )

    @ByVal
    external fun detect(
        @Const @ByRef image: Mat,
        confThreshold: Float,
        iouThreshold: Float
    ): DetectionVector
}
